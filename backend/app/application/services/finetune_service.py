from typing import Any
from uuid import UUID

from app.domain.entities.finetune_job import FinetuneJob
from app.domain.exceptions import FinetuneJobNotFoundError
from app.domain.ports.finetune_repository import FinetuneJobRepository


class FinetuneService:
    def __init__(self, repo: FinetuneJobRepository) -> None:
        self._repo = repo

    async def create(
        self,
        user_id: UUID,
        base_model: str,
        dataset_path: str,
        hyperparams: dict[str, Any],
    ) -> FinetuneJob:
        return await self._repo.create(user_id, base_model, dataset_path, hyperparams)

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

    async def deploy_stub(self, job_id: UUID, user_id: UUID) -> FinetuneJob:
        """Placeholder until Modal/Unsloth integration (Phase 07)."""
        await self.get(job_id, user_id)
        endpoint = f"https://inference.stub.agentforge/job/{job_id}"
        out = await self._repo.set_inference_endpoint(job_id, user_id, endpoint)
        if out is None:
            raise FinetuneJobNotFoundError(str(job_id))
        return out
