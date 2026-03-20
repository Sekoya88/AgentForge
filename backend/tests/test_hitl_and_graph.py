import uuid

import pytest

pytestmark = pytest.mark.usefixtures("alembic_ready")


@pytest.mark.asyncio
async def test_interrupt_pause_and_resume(client) -> None:
    email = f"hitl_{uuid.uuid4().hex[:10]}@example.com"
    await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "longpassword1", "display_name": "H"},
    )
    access = (
        await client.post(
            "/api/v1/auth/login",
            json={"email": email, "password": "longpassword1"},
        )
    ).json()["access_token"]
    headers = {"Authorization": f"Bearer {access}"}

    graph = {
        "nodes": [
            {
                "id": "gate",
                "type": "interrupt",
                "config": {"allowed_decisions": ["approve", "reject"]},
            },
        ],
        "edges": [],
        "entry_point": "gate",
    }
    r = await client.post(
        "/api/v1/agents",
        headers=headers,
        json={
            "name": "HitlAgent",
            "graph_definition": graph,
            "model_config": {"provider": "mock"},
        },
    )
    assert r.status_code == 201, r.text
    agent_id = r.json()["id"]

    r = await client.post(
        f"/api/v1/agents/{agent_id}/execute",
        headers=headers,
        json={"input_messages": [{"role": "user", "content": "hi"}], "run_async": False},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "paused"
    assert body["interrupt_state"]
    exec_id = body["id"]

    r = await client.post(
        f"/api/v1/agents/{agent_id}/executions/{exec_id}/interrupt",
        headers=headers,
        json={"decisions": [{"type": "approve"}]},
    )
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "completed"
    assert r.json()["output_messages"]


@pytest.mark.asyncio
async def test_export_import_roundtrip(client) -> None:
    email = f"ex_{uuid.uuid4().hex[:10]}@example.com"
    await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "longpassword1", "display_name": "E"},
    )
    access = (
        await client.post(
            "/api/v1/auth/login",
            json={"email": email, "password": "longpassword1"},
        )
    ).json()["access_token"]
    headers = {"Authorization": f"Bearer {access}"}

    graph = {
        "nodes": [{"id": "x", "type": "llm", "config": {"prompt": "p"}}],
        "edges": [],
        "entry_point": "x",
    }
    r = await client.post(
        "/api/v1/agents",
        headers=headers,
        json={"name": "Orig", "graph_definition": graph, "model_config": {"provider": "mock"}},
    )
    aid = r.json()["id"]

    r = await client.get(f"/api/v1/agents/{aid}/export", headers=headers)
    assert r.status_code == 200
    blob = r.json()

    r = await client.post(
        "/api/v1/agents/import",
        headers=headers,
        json={**blob, "name": "Cloned"},
    )
    assert r.status_code == 201, r.text
    assert r.json()["name"] == "Cloned"
    assert r.json()["graph_definition"]["entry_point"] == "x"
