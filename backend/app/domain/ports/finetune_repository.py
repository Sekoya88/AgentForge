from abc import ABC, abstractmethod
from typing import Any
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
        agent_id: UUID | None = None,
        *,
        modality: str = "text_sft",
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

    @abstractmethod
    async def update_status(
        self,
        job_id: UUID,
        user_id: UUID,
        status: str,
        modal_job_id: str | None = None,
    ) -> FinetuneJob | None:
        pass

    @abstractmethod
    async def update_metrics(
        self,
        job_id: UUID,
        user_id: UUID,
        metrics: dict[str, Any],
        model_output_path: str | None = None,
    ) -> FinetuneJob | None:
        pass

    @abstractmethod
    async def create_example(
        self,
        agent_id: UUID,
        user_id: UUID,
        execution_id: UUID,
        input_messages: list[dict[str, Any]],
        output_messages: list[dict[str, Any]],
        score: float,
    ) -> Any:
        pass

    @abstractmethod
    async def list_examples_for_agent(
        self,
        agent_id: UUID,
        user_id: UUID,
        min_score: float = 0.8,
    ) -> list[Any]:
        pass
