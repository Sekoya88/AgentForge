from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID

from app.domain.value_objects import FinetuneHyperparams


@dataclass(frozen=True, slots=True)
class FinetuneJob:
    id: UUID
    user_id: UUID | None
    base_model: str
    dataset_path: str
    hyperparams: FinetuneHyperparams
    status: str
    modal_job_id: str | None
    metrics: dict[str, Any] | None
    model_output_path: str | None
    inference_endpoint: str | None
    started_at: datetime | None
    completed_at: datetime | None
    created_at: datetime
