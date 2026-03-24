import asyncio
import json
from typing import Any
from uuid import UUID

from app.config import Settings
from app.domain.entities.finetune_job import FinetuneJob
from app.domain.exceptions import FinetuneJobNotFoundError
from app.domain.ports.finetune_repository import FinetuneJobRepository
from app.domain.value_objects import FinetuneHyperparams


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
    ) -> FinetuneJob:
        hp = FinetuneHyperparams.model_validate(hyperparams)
        job = await self._repo.create(user_id, base_model, dataset_path, hp)

        if getattr(self._settings, "modal_enabled", False):
            import modal

            train_fn = modal.Function.from_name("agentforge-finetune", "train_model")
            hp_dict = hp.to_dict()
            modal_job = await train_fn.spawn.aio(
                str(job.id), job.base_model, job.dataset_path, hp_dict
            )
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
            await _update_status("completed")
            log.info("poll_job_completed", job_id=key)
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
        await self.get(job_id, user_id)

        modal_inference_url = getattr(self._settings, "modal_inference_url", None)
        if modal_inference_url:
            # Real Modal endpoint — callers POST {"job_id": ..., "prompt": ...}
            endpoint = modal_inference_url
        elif getattr(self._settings, "modal_enabled", False):
            # Modal enabled but inference not yet deployed
            endpoint = "https://stub--agentforge-inference-generate.modal.run"
        else:
            endpoint = f"https://inference.stub.agentforge/job/{job_id}"

        out = await self._repo.set_inference_endpoint(job_id, user_id, endpoint)
        if out is None:
            raise FinetuneJobNotFoundError(str(job_id))
        return out
