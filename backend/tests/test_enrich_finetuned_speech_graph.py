"""Tests for AgentService speech finetune graph enrichment (finetune_job_id → endpoint_url)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.application.services.agent_service import AgentService
from app.domain.entities.finetune_job import FinetuneJob
from app.domain.exceptions import FinetuneJobNotFoundError, InvalidSpeechFinetuneJobError
from app.domain.graph_definition import parse_and_validate_graph
from app.domain.value_objects import FinetuneHyperparams


def _job(**kwargs: object) -> FinetuneJob:
    defaults: dict = {
        "id": uuid.uuid4(),
        "user_id": uuid.uuid4(),
        "agent_id": None,
        "base_model": "openai/whisper-large-v3",
        "modality": "whisper",
        "dataset_path": "datasets/x",
        "hyperparams": FinetuneHyperparams(),
        "status": "completed",
        "modal_job_id": None,
        "metrics": None,
        "model_output_path": None,
        "inference_endpoint": "https://example.modal.run/transcribe",
        "started_at": None,
        "completed_at": None,
        "created_at": datetime.now(UTC),
    }
    defaults.update(kwargs)
    return FinetuneJob(**defaults)  # type: ignore[arg-type]


@pytest.fixture
def user_id() -> uuid.UUID:
    return uuid.uuid4()


def _svc(finetune_repo: AsyncMock | None) -> AgentService:
    return AgentService(
        repo=MagicMock(),
        orchestrator=MagicMock(),
        skill_repo=MagicMock(),
        finetune_repo=finetune_repo,
    )


@pytest.mark.asyncio
async def test_enrich_asr_injects_endpoint(user_id: uuid.UUID) -> None:
    jid = uuid.uuid4()
    finetune_repo = AsyncMock()
    finetune_repo.get_by_id = AsyncMock(return_value=_job(id=jid, user_id=user_id))
    svc = _svc(finetune_repo)
    gd = parse_and_validate_graph(
        {
            "nodes": [
                {
                    "id": "listen",
                    "type": "asr",
                    "config": {
                        "provider": "finetuned_whisper",
                        "finetune_job_id": str(jid),
                    },
                },
                {"id": "think", "type": "llm", "config": {}},
            ],
            "edges": [{"from": "listen", "to": "think"}],
            "entry_point": "listen",
        }
    )
    out = await svc._enrich_finetuned_speech_graph(gd, user_id)
    listen = next(n for n in out.nodes if n.id == "listen")
    assert listen.config["endpoint_url"] == "https://example.modal.run/transcribe"
    finetune_repo.get_by_id.assert_awaited_once_with(jid, user_id)


@pytest.mark.asyncio
async def test_enrich_tts_injects_endpoint(user_id: uuid.UUID) -> None:
    jid = uuid.uuid4()
    finetune_repo = AsyncMock()
    finetune_repo.get_by_id = AsyncMock(
        return_value=_job(
            id=jid,
            user_id=user_id,
            modality="tts_voice",
            inference_endpoint="https://example.modal.run/speak",
        )
    )
    svc = _svc(finetune_repo)
    gd = parse_and_validate_graph(
        {
            "nodes": [
                {"id": "think", "type": "llm", "config": {}},
                {
                    "id": "speak",
                    "type": "tts",
                    "config": {"provider": "finetuned_tts", "finetune_job_id": str(jid)},
                },
            ],
            "edges": [{"from": "think", "to": "speak"}],
            "entry_point": "think",
        }
    )
    out = await svc._enrich_finetuned_speech_graph(gd, user_id)
    speak = next(n for n in out.nodes if n.id == "speak")
    assert speak.config["endpoint_url"] == "https://example.modal.run/speak"


@pytest.mark.asyncio
async def test_enrich_skips_when_endpoint_url_set(user_id: uuid.UUID) -> None:
    jid = uuid.uuid4()
    finetune_repo = AsyncMock()
    finetune_repo.get_by_id = AsyncMock(return_value=_job(id=jid, user_id=user_id))
    svc = _svc(finetune_repo)
    gd = parse_and_validate_graph(
        {
            "nodes": [
                {
                    "id": "listen",
                    "type": "asr",
                    "config": {
                        "provider": "finetuned_whisper",
                        "finetune_job_id": str(jid),
                        "endpoint_url": "https://manual.example/run",
                    },
                },
                {"id": "x", "type": "llm", "config": {}},
            ],
            "edges": [{"from": "listen", "to": "x"}],
            "entry_point": "listen",
        }
    )
    out = await svc._enrich_finetuned_speech_graph(gd, user_id)
    listen = next(n for n in out.nodes if n.id == "listen")
    assert listen.config["endpoint_url"] == "https://manual.example/run"
    finetune_repo.get_by_id.assert_not_called()


@pytest.mark.asyncio
async def test_enrich_no_finetune_repo_unchanged(user_id: uuid.UUID) -> None:
    svc = _svc(finetune_repo=None)
    gd = parse_and_validate_graph(
        {
            "nodes": [
                {
                    "id": "listen",
                    "type": "asr",
                    "config": {
                        "provider": "finetuned_whisper",
                        "finetune_job_id": str(uuid.uuid4()),
                    },
                },
                {"id": "x", "type": "llm", "config": {}},
            ],
            "edges": [{"from": "listen", "to": "x"}],
            "entry_point": "listen",
        }
    )
    out = await svc._enrich_finetuned_speech_graph(gd, user_id)
    listen = next(n for n in out.nodes if n.id == "listen")
    assert "endpoint_url" not in listen.config


@pytest.mark.asyncio
async def test_wrong_modality_raises(user_id: uuid.UUID) -> None:
    jid = uuid.uuid4()
    finetune_repo = AsyncMock()
    finetune_repo.get_by_id = AsyncMock(
        return_value=_job(id=jid, user_id=user_id, modality="text_sft")
    )
    svc = _svc(finetune_repo)
    gd = parse_and_validate_graph(
        {
            "nodes": [
                {
                    "id": "listen",
                    "type": "asr",
                    "config": {"provider": "finetuned_whisper", "finetune_job_id": str(jid)},
                },
                {"id": "x", "type": "llm", "config": {}},
            ],
            "edges": [{"from": "listen", "to": "x"}],
            "entry_point": "listen",
        }
    )
    with pytest.raises(InvalidSpeechFinetuneJobError, match="modality"):
        await svc._enrich_finetuned_speech_graph(gd, user_id)


@pytest.mark.asyncio
async def test_missing_job_raises(user_id: uuid.UUID) -> None:
    jid = uuid.uuid4()
    finetune_repo = AsyncMock()
    finetune_repo.get_by_id = AsyncMock(return_value=None)
    svc = _svc(finetune_repo)
    gd = parse_and_validate_graph(
        {
            "nodes": [
                {
                    "id": "listen",
                    "type": "asr",
                    "config": {"provider": "finetuned_whisper", "finetune_job_id": str(jid)},
                },
                {"id": "x", "type": "llm", "config": {}},
            ],
            "edges": [{"from": "listen", "to": "x"}],
            "entry_point": "listen",
        }
    )
    with pytest.raises(FinetuneJobNotFoundError):
        await svc._enrich_finetuned_speech_graph(gd, user_id)


@pytest.mark.asyncio
async def test_incomplete_job_raises(user_id: uuid.UUID) -> None:
    jid = uuid.uuid4()
    finetune_repo = AsyncMock()
    finetune_repo.get_by_id = AsyncMock(
        return_value=_job(id=jid, user_id=user_id, status="running")
    )
    svc = _svc(finetune_repo)
    gd = parse_and_validate_graph(
        {
            "nodes": [
                {
                    "id": "listen",
                    "type": "asr",
                    "config": {"provider": "finetuned_whisper", "finetune_job_id": str(jid)},
                },
                {"id": "x", "type": "llm", "config": {}},
            ],
            "edges": [{"from": "listen", "to": "x"}],
            "entry_point": "listen",
        }
    )
    with pytest.raises(InvalidSpeechFinetuneJobError, match="status"):
        await svc._enrich_finetuned_speech_graph(gd, user_id)
