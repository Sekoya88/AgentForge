from abc import ABC, abstractmethod
from uuid import UUID

from app.domain.entities.finetune_job import FinetuneJob
from app.domain.value_objects import FinetuneHyperparams


class FinetuneJobRepository(ABC):
    @abstractmethod
    async def create(
        self,
        user_id: UUID,
        base_model: str,
        dataset_path: str,
        hyperparams: FinetuneHyperparams,
    ) -> FinetuneJob:
        pass

    @abstractmethod
    async def list_for_user(self, user_id: UUID) -> list[FinetuneJob]:
        pass

    @abstractmethod
    async def get_by_id(self, job_id: UUID, user_id: UUID) -> FinetuneJob | None:
        pass

    @abstractmethod
    async def delete(self, job_id: UUID, user_id: UUID) -> bool:
        pass

    @abstractmethod
    async def set_inference_endpoint(
        self,
        job_id: UUID,
        user_id: UUID,
        endpoint: str,
    ) -> FinetuneJob | None:
        pass
