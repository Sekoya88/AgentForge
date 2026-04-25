from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from app.domain.entities.finetune_job import FinetuneJob


class FinetuneTriggerRequest(BaseModel):
    agent_id: UUID
    base_model: str = "unsloth/llama-3-8b-Instruct"
    min_score: float = 0.8


class FinetuneCreateRequest(BaseModel):
    base_model: str = Field(min_length=1, max_length=255)
    modality: str = Field(
        default="text_sft",
        max_length=32,
        description=(
            "text_sft: Unsloth LLM SFT (train_model). "
            "whisper / tts_voice: speech stubs "
            "(train_speech_model on Modal app agentforge-finetune)."
        ),
    )
    dataset_path: str = Field(
        min_length=1,
        max_length=500,
        description=(
            "Hub: hf://org/dataset or hf://org/dataset/config (e.g. hf://openai/gsm8k/main). "
            "Multi-config datasets auto-pick 'main' when omitted."
        ),
    )
    hyperparams: dict[str, Any] = Field(default_factory=dict)


class FinetuneJobResponse(BaseModel):
    id: UUID
    user_id: UUID | None
    base_model: str
    modality: str
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
            modality=j.modality,
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
