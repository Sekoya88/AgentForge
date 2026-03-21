from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities.finetune_job import FinetuneJob
from app.domain.ports.finetune_repository import FinetuneJobRepository
from app.domain.value_objects import FinetuneHyperparams
from app.infrastructure.persistence.postgres.models import FinetuneJobModel


class PostgresFinetuneJobRepository(FinetuneJobRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        user_id: UUID,
        base_model: str,
        dataset_path: str,
        hyperparams: FinetuneHyperparams,
    ) -> FinetuneJob:
        m = FinetuneJobModel(
            user_id=user_id,
            base_model=base_model,
            dataset_path=dataset_path,
            hyperparams=hyperparams.to_dict(),
            status="pending",
        )
        self._session.add(m)
        await self._session.flush()
        await self._session.refresh(m)
        return self._to_entity(m)

    async def list_for_user(self, user_id: UUID) -> list[FinetuneJob]:
        q = await self._session.execute(
            select(FinetuneJobModel)
            .where(FinetuneJobModel.user_id == user_id)
            .order_by(FinetuneJobModel.created_at.desc())
        )
        return [self._to_entity(r) for r in q.scalars().all()]

    async def get_by_id(self, job_id: UUID, user_id: UUID) -> FinetuneJob | None:
        m = await self._session.get(FinetuneJobModel, job_id)
        if m is None or m.user_id != user_id:
            return None
        return self._to_entity(m)

    async def delete(self, job_id: UUID, user_id: UUID) -> bool:
        m = await self._session.get(FinetuneJobModel, job_id)
        if m is None or m.user_id != user_id:
            return False
        await self._session.delete(m)
        return True

    async def set_inference_endpoint(
        self,
        job_id: UUID,
        user_id: UUID,
        endpoint: str,
    ) -> FinetuneJob | None:
        m = await self._session.get(FinetuneJobModel, job_id)
        if m is None or m.user_id != user_id:
            return None
        m.inference_endpoint = endpoint
        await self._session.flush()
        await self._session.refresh(m)
        return self._to_entity(m)

    @staticmethod
    def _to_entity(m: FinetuneJobModel) -> FinetuneJob:
        return FinetuneJob(
            id=m.id,
            user_id=m.user_id,
            base_model=m.base_model,
            dataset_path=m.dataset_path,
            hyperparams=FinetuneHyperparams.model_validate(m.hyperparams),
            status=m.status or "pending",
            modal_job_id=m.modal_job_id,
            metrics=dict(m.metrics) if m.metrics else None,
            model_output_path=m.model_output_path,
            inference_endpoint=m.inference_endpoint,
            started_at=m.started_at,
            completed_at=m.completed_at,
            created_at=m.created_at,
        )
