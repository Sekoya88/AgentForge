from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from app.domain.entities.finetune_job import FinetuneJob


class FinetuneCreateRequest(BaseModel):
    base_model: str = Field(min_length=1, max_length=255)
    dataset_path: str = Field(min_length=1, max_length=500)
    hyperparams: dict[str, Any] = Field(default_factory=dict)


class FinetuneJobResponse(BaseModel):
    id: UUID
    user_id: UUID | None
    base_model: str
    dataset_path: str
    hyperparams: dict[str, Any]
    status: str
    modal_job_id: str | None
    metrics: dict[str, Any] | None
    model_output_path: str | None
    inference_endpoint: str | None
    started_at: datetime | None
    completed_at: datetime | None
    created_at: datetime

    @classmethod
    def from_entity(cls, j: FinetuneJob) -> "FinetuneJobResponse":
        return cls(
            id=j.id,
            user_id=j.user_id,
            base_model=j.base_model,
            dataset_path=j.dataset_path,
            hyperparams=j.hyperparams.to_dict(),
            status=j.status,
            modal_job_id=j.modal_job_id,
            metrics=j.metrics,
            model_output_path=j.model_output_path,
            inference_endpoint=j.inference_endpoint,
            started_at=j.started_at,
            completed_at=j.completed_at,
            created_at=j.created_at,
        )
