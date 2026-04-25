import asyncio
import json
from typing import Any
from uuid import UUID

import structlog

from app.config import Settings
from app.domain.entities.finetune_job import FinetuneJob
from app.domain.exceptions import FinetuneJobNotFoundError, ModalNotInstalledError
from app.domain.ports.finetune_repository import FinetuneJobRepository
from app.domain.value_objects import FinetuneHyperparams
from app.infrastructure.webhooks.delivery import schedule_finetune_completed_webhook


def _modal_dict_read(metrics_dict: Any, key: str) -> dict[str, Any] | None:
    """Sync read from Modal Dict (client handle); run via asyncio.to_thread."""
    try:
        raw = metrics_dict.get(key) if hasattr(metrics_dict, "get") else metrics_dict[key]
    except KeyError:
        return None
    if raw is None:
        return None
    if isinstance(raw, dict):
        return raw
    return dict(raw) if hasattr(raw, "keys") else {"value": raw}


class FinetuneService:
    def __init__(
        self,
        repo: FinetuneJobRepository,
        settings: Settings,
        redis_client: Any | None = None,
    ) -> None:
        self._repo = repo
        self._settings = settings
        self._redis_client = redis_client

    async def create(
        self,
        user_id: UUID,
        base_model: str,
        dataset_path: str,
        hyperparams: dict[str, Any],
        agent_id: UUID | None = None,
        *,
        modality: str = "text_sft",
    ) -> FinetuneJob:
        hp = FinetuneHyperparams.model_validate(hyperparams)
        mod = modality.strip().lower() if modality else "text_sft"
        if mod not in ("text_sft", "whisper", "tts_voice"):
            raise ValueError(f"Unsupported modality {modality!r}")

        job = await self._repo.create(
            user_id,
            base_model,
            dataset_path,
            hp,
            agent_id=agent_id,
            modality=mod,
        )

        if getattr(self._settings, "modal_enabled", False):
            try:
                import modal
            except ImportError as e:
                raise ModalNotInstalledError(
                    "MODAL_ENABLED is true but the 'modal' package is not installed. "
                    "Run: cd backend && uv pip install -e ."
                ) from e

            log = structlog.get_logger()
            hp_dict = hp.to_dict()
            try:
                if mod == "text_sft":
                    train_fn = modal.Function.from_name("agentforge-finetune", "train_model")
                    modal_job = await train_fn.spawn.aio(
                        str(job.id), job.base_model, job.dataset_path, hp_dict
                    )
                else:
                    # Same Modal app as LLM SFT; deploy: modal deploy .../train.py
                    train_fn = modal.Function.from_name("agentforge-finetune", "train_speech_model")
                    modal_job = await train_fn.spawn.aio(
                        str(job.id),
                        mod,
                        job.base_model,
                        job.dataset_path,
                        hp_dict,
                    )
            except modal.exception.NotFoundError as e:
                log.warning(
                    "modal_finetune_function_missing",
                    modality=mod,
                    error=str(e),
                    hint="Redeploy: modal deploy backend/modal_functions/train.py",
                )
                await self._repo.update_status(job.id, user_id, "pending")
                fresh = await self._repo.get_by_id(job.id, user_id)
                return fresh if fresh is not None else job

            updated_job = await self._repo.update_status(
                job.id, user_id, "running", modal_job_id=modal_job.object_id
            )
            if updated_job:
                job = updated_job
            asyncio.create_task(self._poll_job(job.id, user_id, modal_job.object_id))
        else:
            await self._repo.update_status(job.id, user_id, "pending")

        return job

    async def _poll_job(self, job_id: UUID, user_id: UUID, modal_job_id: str) -> None:
        import modal
        import structlog

        from app.infrastructure.persistence.postgres.finetune_repo import (
            PostgresFinetuneJobRepository,
        )
        from app.infrastructure.persistence.postgres.session import session_scope

        log = structlog.get_logger()
        call = modal.FunctionCall.from_id(modal_job_id)
        metrics_dict = modal.Dict.from_name("agentforge-metrics", create_if_missing=True)
        key = str(job_id)

        async def _update_metrics(metrics: dict[str, Any]) -> None:
            path = metrics.get("model_output_path")
            snapshot = {k: v for k, v in metrics.items() if k != "model_output_path"}
            async with session_scope() as sess:
                repo = PostgresFinetuneJobRepository(sess)
                # Read existing metrics to append history
                existing = await repo.get_by_id(job_id, user_id)
                prev = dict(existing.metrics) if existing and existing.metrics else {}
                history: list[dict] = prev.get("history", [])
                # Append snapshot (dedupe by step)
                step = snapshot.get("step")
                if not history or history[-1].get("step") != step:
                    history.append(snapshot)
                # Store latest values at top level + full history
                payload = {**snapshot, "history": history}
                await repo.update_metrics(
                    job_id,
                    user_id,
                    payload,
                    model_output_path=path if isinstance(path, str) else None,
                )
            if self._redis_client is not None:
                pub = json.dumps({"type": "metrics", "data": metrics})
                await self._redis_client.publish(f"finetune:{job_id}", pub)

        async def _update_status(status: str) -> None:
            async with session_scope() as sess:
                repo = PostgresFinetuneJobRepository(sess)
                await repo.update_status(job_id, user_id, status)
            if self._redis_client is not None:
                await self._redis_client.publish(
                    f"finetune:{job_id}",
                    json.dumps({"type": status}),
                )

        while True:
            try:
                await call.get.aio(timeout=0)
            except TimeoutError:
                metrics = await asyncio.to_thread(_modal_dict_read, metrics_dict, key)
                if metrics is not None:
                    await _update_metrics(metrics)
                    log.info("poll_metrics", job_id=key, metrics=metrics)
                await asyncio.sleep(10)
                continue
            except Exception:
                log.exception("poll_job_failed", job_id=key)
                await _update_status("failed")
                break

            # Completed without TimeoutError
            final = await asyncio.to_thread(_modal_dict_read, metrics_dict, key)
            if final:
                await _update_metrics(final)
                ie = final.get("inference_endpoint") if isinstance(final, dict) else None
                if isinstance(ie, str) and ie.strip():
                    async with session_scope() as sess:
                        ep_repo = PostgresFinetuneJobRepository(sess)
                        await ep_repo.set_inference_endpoint(job_id, user_id, ie.strip())
            await _update_status("completed")
            log.info("poll_job_completed", job_id=key)
            schedule_finetune_completed_webhook(
                user_id,
                {"job_id": key},
            )

            # Auto-Deploy Finetuned Model to shadow alias
            # Use a fresh DB session — self._repo is bound to the HTTP request session
            # which is already closed when this background task runs.
            try:
                async with session_scope() as deploy_sess:
                    deploy_repo = PostgresFinetuneJobRepository(deploy_sess)
                    fresh_svc = FinetuneService(deploy_repo, self._settings, self._redis_client)
                    job = await fresh_svc.deploy(UUID(key), user_id)
                if job.agent_id:
                    from app.domain.value_objects import AgentModelConfig
                    from app.infrastructure.persistence.postgres.agent_repo import (
                        PostgresAgentRepository,
                    )

                    async with session_scope() as sess:
                        agent_repo = PostgresAgentRepository(sess)
                        agent = await agent_repo.get_by_id(job.agent_id, user_id)
                        if agent:
                            # Update the agent's model config
                            new_mc = agent.model_config.to_dict()
                            new_mc["provider"] = "finetuned"
                            new_mc["model"] = job.base_model
                            new_mc["finetune_job_id"] = str(job.id)

                            updated_agent = await agent_repo.update(
                                agent_id=agent.id,
                                user_id=user_id,
                                name=None,
                                description=None,
                                graph_definition=None,
                                model_config=AgentModelConfig.model_validate(new_mc),
                                status=None,
                            )
                            if updated_agent:
                                # Get the new version number
                                new_v = await agent_repo.get_latest_version_number(agent.id)
                                # Set shadow alias
                                await agent_repo.set_alias(agent.id, user_id, "shadow", new_v)
                                log.info(
                                    "auto_deployed_shadow_alias",
                                    agent_id=str(agent.id),
                                    version=new_v,
                                )
            except Exception:
                log.exception("auto_deploy_failed", job_id=key)

            break

    async def list_jobs(self, user_id: UUID) -> list[FinetuneJob]:
        return await self._repo.list_for_user(user_id)

    async def get(self, job_id: UUID, user_id: UUID) -> FinetuneJob:
        j = await self._repo.get_by_id(job_id, user_id)
        if j is None:
            raise FinetuneJobNotFoundError(str(job_id))
        return j

    async def delete(self, job_id: UUID, user_id: UUID) -> None:
        ok = await self._repo.delete(job_id, user_id)
        if not ok:
            raise FinetuneJobNotFoundError(str(job_id))

    async def cancel(self, job_id: UUID, user_id: UUID) -> None:
        """Cancel a fine-tune job."""
        job = await self.get(job_id, user_id)
        if getattr(self._settings, "modal_enabled", False) and job.modal_job_id:
            import modal

            try:
                call = modal.FunctionCall.from_id(job.modal_job_id)
                await call.cancel.aio()
            except Exception:
                pass  # Ignore cancel errors if job is already done or modal is unreachable

        out = await self._repo.update_status(job_id, user_id, "cancelled")
        if out is None:
            raise FinetuneJobNotFoundError(str(job_id))

    async def deploy(self, job_id: UUID, user_id: UUID) -> FinetuneJob:
        """Register inference endpoint for a completed fine-tune job.

        If MODAL_INFERENCE_URL is set (after `modal deploy inference.py`),
        that URL is used as the base endpoint. Otherwise falls back to a
        deterministic stub URL for local/dev use.
        """
        job = await self.get(job_id, user_id)
        if job.inference_endpoint and str(job.inference_endpoint).strip():
            return job

        modal_inference_url = getattr(self._settings, "modal_inference_url", None)
        if modal_inference_url:
            # Real Modal endpoint — callers POST {"job_id": ..., "prompt": ...}
            endpoint = modal_inference_url
        elif getattr(self._settings, "modal_enabled", False):
            # Modal enabled but inference not yet deployed
            endpoint = "https://stub--agentforge-inference-generate.modal.run"
        else:
            m = (job.modality or "text_sft").lower()
            if m == "whisper":
                endpoint = f"https://inference.stub.agentforge/speech/whisper/{job_id}"
            elif m == "tts_voice":
                endpoint = f"https://inference.stub.agentforge/speech/tts/{job_id}"
            else:
                endpoint = f"https://inference.stub.agentforge/job/{job_id}"

        out = await self._repo.set_inference_endpoint(job_id, user_id, endpoint)
        if out is None:
            raise FinetuneJobNotFoundError(str(job_id))
        return out

    async def save_example(
        self,
        agent_id: UUID,
        user_id: UUID,
        execution_id: UUID,
        input_messages: list[dict[str, Any]],
        output_messages: list[dict[str, Any]],
        score: float,
    ) -> Any:
        return await self._repo.create_example(
            agent_id, user_id, execution_id, input_messages, output_messages, score
        )

    async def trigger_auto_finetune(
        self,
        agent_id: UUID,
        user_id: UUID,
        base_model: str = "unsloth/llama-3-8b-Instruct",
        dataset_path: str = "/tmp/auto_finetune.jsonl",
        min_score: float = 0.8,
    ) -> FinetuneJob:
        examples = await self._repo.list_examples_for_agent(agent_id, user_id, min_score)
        if not examples:
            raise ValueError("Not enough high-quality examples to trigger finetuning")

        import json

        # Write dataset to a local JSONL file first
        with open(dataset_path, "w") as f:
            for ex in examples:
                # Format as ShareGPT or simple messages format.
                # Assuming simple standard messages for Llama Instruct
                msgs = [{"role": m["role"], "content": m["content"]} for m in ex.input_messages]
                # append assistant output
                for om in ex.output_messages:
                    msgs.append({"role": "assistant", "content": om["content"]})

                f.write(json.dumps({"messages": msgs}) + "\n")

        # Now trigger the regular create
        hp = {"epochs": 3, "batch_size": 2, "learning_rate": 2e-4}
        return await self.create(user_id, base_model, dataset_path, hp, agent_id=agent_id)
