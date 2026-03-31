"""
Integration tests for fine-tuning endpoints.

Covers:
- CRUD (create, list, get, delete)
- Status/metrics updates via repo
- deploy() — stub URL in non-Modal mode
- cancel endpoint
- Auth isolation (user can't access another user's jobs)
- FinetuneService with mocked Modal (no GPU required)
"""

import uuid
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytestmark = pytest.mark.usefixtures("alembic_ready")

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _register_login(client, suffix: str = "") -> tuple[str, str]:
    """Register a user and return (user_id, access_token)."""
    email = f"finetune_{uuid.uuid4().hex[:8]}{suffix}@example.com"
    r = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "strongpassword1", "display_name": "FT"},
    )
    assert r.status_code == 200, r.text
    user_id: str = r.json()["id"]

    r = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "strongpassword1"},
    )
    assert r.status_code == 200, r.text
    token: str = r.json()["access_token"]
    return user_id, token


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


_CREATE_BODY: dict[str, Any] = {
    "base_model": "unsloth/llama-3.2-1b-instruct",
    "dataset_path": "hf://trl-lib/Capybara",
    "hyperparams": {"epochs": 1, "learning_rate": 2e-4, "batch_size": 2},
}

# ---------------------------------------------------------------------------
# CRUD — basic lifecycle
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_and_list(client) -> None:
    _, token = await _register_login(client)

    r = await client.post("/api/v1/finetune", headers=_auth(token), json=_CREATE_BODY)
    assert r.status_code == 201, r.text
    assert r.json().get("modality") == "text_sft"
    job = r.json()
    assert job["base_model"] == _CREATE_BODY["base_model"]
    assert job["dataset_path"] == _CREATE_BODY["dataset_path"]
    assert job["status"] in ("pending", "running")
    assert job["inference_endpoint"] is None
    job_id = job["id"]

    r = await client.get("/api/v1/finetune", headers=_auth(token))
    assert r.status_code == 200
    ids = [j["id"] for j in r.json()]
    assert job_id in ids


@pytest.mark.asyncio
async def test_create_rejects_unsupported_modality(client) -> None:
    _, token = await _register_login(client)
    body = {**_CREATE_BODY, "modality": "asr_whisper"}
    r = await client.post("/api/v1/finetune", headers=_auth(token), json=body)
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_create_whisper_modality_pending_without_modal(client) -> None:
    _, token = await _register_login(client)
    body = {
        **_CREATE_BODY,
        "modality": "whisper",
        "dataset_path": "speech://export/examples.jsonl",
    }
    r = await client.post("/api/v1/finetune", headers=_auth(token), json=body)
    assert r.status_code == 201, r.text
    j = r.json()
    assert j["modality"] == "whisper"
    assert j["status"] == "pending"


@pytest.mark.asyncio
async def test_create_tts_voice_modality_pending_without_modal(client) -> None:
    _, token = await _register_login(client)
    body = {
        **_CREATE_BODY,
        "modality": "tts_voice",
        "dataset_path": "speech://voice_samples",
    }
    r = await client.post("/api/v1/finetune", headers=_auth(token), json=body)
    assert r.status_code == 201, r.text
    assert r.json()["modality"] == "tts_voice"


@pytest.mark.asyncio
async def test_get_single(client) -> None:
    _, token = await _register_login(client)

    r = await client.post("/api/v1/finetune", headers=_auth(token), json=_CREATE_BODY)
    assert r.status_code == 201
    job_id = r.json()["id"]

    r = await client.get(f"/api/v1/finetune/{job_id}", headers=_auth(token))
    assert r.status_code == 200
    assert r.json()["id"] == job_id


@pytest.mark.asyncio
async def test_get_not_found(client) -> None:
    _, token = await _register_login(client)
    fake_id = str(uuid.uuid4())
    r = await client.get(f"/api/v1/finetune/{fake_id}", headers=_auth(token))
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_delete(client) -> None:
    _, token = await _register_login(client)

    r = await client.post("/api/v1/finetune", headers=_auth(token), json=_CREATE_BODY)
    assert r.status_code == 201
    job_id = r.json()["id"]

    r = await client.delete(f"/api/v1/finetune/{job_id}", headers=_auth(token))
    assert r.status_code == 204

    r = await client.get(f"/api/v1/finetune/{job_id}", headers=_auth(token))
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_delete_not_found(client) -> None:
    _, token = await _register_login(client)
    fake_id = str(uuid.uuid4())
    r = await client.delete(f"/api/v1/finetune/{fake_id}", headers=_auth(token))
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# Hyperparams stored and returned correctly
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_hyperparams_roundtrip(client) -> None:
    _, token = await _register_login(client)
    hp = {"epochs": 3, "learning_rate": 5e-5, "batch_size": 4}
    body = {**_CREATE_BODY, "hyperparams": hp}

    r = await client.post("/api/v1/finetune", headers=_auth(token), json=body)
    assert r.status_code == 201
    got_hp = r.json()["hyperparams"]
    assert got_hp["epochs"] == 3
    assert abs(got_hp["learning_rate"] - 5e-5) < 1e-10
    assert got_hp["batch_size"] == 4


@pytest.mark.asyncio
async def test_hyperparams_defaults(client) -> None:
    _, token = await _register_login(client)
    body = {**_CREATE_BODY, "hyperparams": {}}  # all defaults

    r = await client.post("/api/v1/finetune", headers=_auth(token), json=body)
    assert r.status_code == 201
    # Should not crash — null values are fine
    hp = r.json()["hyperparams"]
    assert isinstance(hp, dict)


# ---------------------------------------------------------------------------
# Deploy — stub URL (no Modal)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_deploy_stub(client) -> None:
    _, token = await _register_login(client)

    r = await client.post("/api/v1/finetune", headers=_auth(token), json=_CREATE_BODY)
    assert r.status_code == 201
    job_id = r.json()["id"]

    r = await client.post(f"/api/v1/finetune/{job_id}/deploy", headers=_auth(token))
    assert r.status_code == 200
    job = r.json()
    assert job["inference_endpoint"] is not None
    assert "stub" in job["inference_endpoint"] or "modal" in job["inference_endpoint"]


@pytest.mark.asyncio
async def test_deploy_not_found(client) -> None:
    _, token = await _register_login(client)
    fake_id = str(uuid.uuid4())
    r = await client.post(f"/api/v1/finetune/{fake_id}/deploy", headers=_auth(token))
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# Cancel
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cancel(client) -> None:
    _, token = await _register_login(client)

    r = await client.post("/api/v1/finetune", headers=_auth(token), json=_CREATE_BODY)
    assert r.status_code == 201
    job_id = r.json()["id"]

    r = await client.delete(f"/api/v1/finetune/{job_id}/cancel", headers=_auth(token))
    assert r.status_code == 204

    r = await client.get(f"/api/v1/finetune/{job_id}", headers=_auth(token))
    assert r.status_code == 200
    assert r.json()["status"] == "cancelled"


@pytest.mark.asyncio
async def test_cancel_not_found(client) -> None:
    _, token = await _register_login(client)
    fake_id = str(uuid.uuid4())
    r = await client.delete(f"/api/v1/finetune/{fake_id}/cancel", headers=_auth(token))
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# Auth isolation — user B cannot access user A's jobs
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_auth_isolation(client) -> None:
    _, token_a = await _register_login(client, "_a")
    _, token_b = await _register_login(client, "_b")

    r = await client.post("/api/v1/finetune", headers=_auth(token_a), json=_CREATE_BODY)
    assert r.status_code == 201
    job_id = r.json()["id"]

    # B cannot get A's job
    r = await client.get(f"/api/v1/finetune/{job_id}", headers=_auth(token_b))
    assert r.status_code == 404

    # B's list is empty
    r = await client.get("/api/v1/finetune", headers=_auth(token_b))
    assert r.status_code == 200
    assert all(j["id"] != job_id for j in r.json())

    # B cannot delete A's job
    r = await client.delete(f"/api/v1/finetune/{job_id}", headers=_auth(token_b))
    assert r.status_code == 404

    # B cannot cancel A's job
    r = await client.delete(f"/api/v1/finetune/{job_id}/cancel", headers=_auth(token_b))
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# Unauthenticated requests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_unauthenticated(client) -> None:
    r = await client.get("/api/v1/finetune")
    assert r.status_code == 401

    r = await client.post("/api/v1/finetune", json=_CREATE_BODY)
    assert r.status_code == 401


# ---------------------------------------------------------------------------
# FinetuneService — Modal mocked (no real GPU)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_service_spawns_modal_when_enabled(client, db_session) -> None:
    """Service.create() spawns Modal and polls when MODAL_ENABLED=true."""
    from uuid import uuid4

    from app.application.services.finetune_service import FinetuneService
    from app.config import Settings
    from app.infrastructure.persistence.postgres.finetune_repo import (
        PostgresFinetuneJobRepository,
    )

    # Register user to get a real UUID
    email = f"svc_modal_{uuid4().hex[:8]}@example.com"
    import hashlib

    from app.infrastructure.persistence.postgres.models import UserModel

    user_model = UserModel(
        email=email,
        hashed_password=hashlib.sha256(b"pw").hexdigest(),
        display_name="SvcModal",
    )
    db_session.add(user_model)
    await db_session.flush()
    await db_session.refresh(user_model)
    user_id = user_model.id

    settings = Settings(
        _env_file=None,  # type: ignore[call-arg]
        DATABASE_URL="postgresql+asyncpg://forge:forge@localhost:5433/agentforge",
        MODAL_ENABLED=True,
    )

    repo = PostgresFinetuneJobRepository(db_session)
    redis_mock = AsyncMock()
    redis_mock.publish = AsyncMock()
    svc = FinetuneService(repo=repo, settings=settings, redis_client=redis_mock)

    # Mock Modal train_model.spawn
    mock_call = MagicMock()
    mock_call.object_id = "modal-fake-object-id"

    with (
        patch("app.application.services.finetune_service.asyncio.create_task") as mock_task,
        patch.dict(
            "sys.modules",
            {
                "modal_functions.train": MagicMock(
                    train_model=MagicMock(spawn=MagicMock(return_value=mock_call))
                )
            },
        ),
    ):
        job = await svc.create(
            user_id=user_id,
            base_model="unsloth/llama-3.2-1b-instruct",
            dataset_path="hf://trl-lib/Capybara",
            hyperparams={"epochs": 1},
        )

    assert job.status == "running"
    assert job.modal_job_id == "modal-fake-object-id"
    mock_task.assert_called_once()  # background poll task spawned


@pytest.mark.asyncio
async def test_service_pending_when_modal_disabled(client, db_session) -> None:
    """Service.create() stays pending when MODAL_ENABLED=false."""
    import hashlib
    from uuid import uuid4

    from app.application.services.finetune_service import FinetuneService
    from app.config import Settings
    from app.infrastructure.persistence.postgres.finetune_repo import (
        PostgresFinetuneJobRepository,
    )
    from app.infrastructure.persistence.postgres.models import UserModel

    email = f"svc_nomoda_{uuid4().hex[:8]}@example.com"
    user_model = UserModel(
        email=email,
        hashed_password=hashlib.sha256(b"pw").hexdigest(),
        display_name="NoModal",
    )
    db_session.add(user_model)
    await db_session.flush()
    await db_session.refresh(user_model)
    user_id = user_model.id

    settings = Settings(
        _env_file=None,  # type: ignore[call-arg]
        DATABASE_URL="postgresql+asyncpg://forge:forge@localhost:5433/agentforge",
        MODAL_ENABLED=False,
    )

    repo = PostgresFinetuneJobRepository(db_session)
    svc = FinetuneService(repo=repo, settings=settings)

    job = await svc.create(
        user_id=user_id,
        base_model="unsloth/llama-3.2-1b-instruct",
        dataset_path="hf://trl-lib/Capybara",
        hyperparams={},
    )
    assert job.status == "pending"
    assert job.modal_job_id is None


@pytest.mark.asyncio
async def test_repo_update_status_and_metrics(db_session) -> None:
    """update_status and update_metrics work correctly on Postgres."""
    import hashlib
    from uuid import uuid4

    from app.domain.value_objects import FinetuneHyperparams
    from app.infrastructure.persistence.postgres.finetune_repo import (
        PostgresFinetuneJobRepository,
    )
    from app.infrastructure.persistence.postgres.models import UserModel

    email = f"repo_test_{uuid4().hex[:8]}@example.com"
    user_model = UserModel(
        email=email,
        hashed_password=hashlib.sha256(b"pw").hexdigest(),
        display_name="Repo",
    )
    db_session.add(user_model)
    await db_session.flush()
    await db_session.refresh(user_model)
    user_id = user_model.id

    repo = PostgresFinetuneJobRepository(db_session)
    hp = FinetuneHyperparams(epochs=1, learning_rate=2e-4, batch_size=2, max_steps=None)
    job = await repo.create(user_id, "llama-1b", "hf://dataset", hp)
    assert job.modality == "text_sft"

    # update_status
    updated = await repo.update_status(job.id, user_id, "running", modal_job_id="m-123")
    assert updated is not None
    assert updated.status == "running"
    assert updated.modal_job_id == "m-123"

    # update_metrics
    metrics = {"loss": 0.42, "epoch": 1.0, "step": 60}
    updated = await repo.update_metrics(
        job.id, user_id, metrics, model_output_path="/data/models/x"
    )
    assert updated is not None
    assert updated.metrics == metrics
    assert updated.model_output_path == "/data/models/x"

    # update_status for wrong user returns None
    wrong = await repo.update_status(job.id, uuid4(), "completed")
    assert wrong is None
