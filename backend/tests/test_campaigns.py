import uuid

import pytest

pytestmark = pytest.mark.usefixtures("alembic_ready")


@pytest.mark.asyncio
async def test_campaign_sync_updates_agent_security_score(client) -> None:
    email = f"camp_{uuid.uuid4().hex[:10]}@example.com"
    r = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "longpassword1", "display_name": "C"},
    )
    assert r.status_code == 200, r.text
    access = (
        await client.post(
            "/api/v1/auth/login",
            json={"email": email, "password": "longpassword1"},
        )
    ).json()["access_token"]

    graph = {
        "nodes": [{"id": "a", "type": "llm", "config": {"prompt": "x"}}],
        "edges": [],
        "entry_point": "a",
    }
    r = await client.post(
        "/api/v1/agents",
        headers={"Authorization": f"Bearer {access}"},
        json={
            "name": "RedTarget",
            "graph_definition": graph,
            "model_config": {"provider": "mock"},
        },
    )
    assert r.status_code == 201, r.text
    agent_id = r.json()["id"]

    r = await client.post(
        "/api/v1/campaigns",
        headers={"Authorization": f"Bearer {access}"},
        json={
            "agent_id": agent_id,
            "plugins": ["default"],
            "strategies": ["basic"],
            "run_async": False,
        },
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["status"] == "completed"
    assert body["overall_score"] is not None
    assert body["total_tests"] == 12
    assert body["report"] is not None

    r = await client.get(
        f"/api/v1/agents/{agent_id}",
        headers={"Authorization": f"Bearer {access}"},
    )
    assert r.status_code == 200
    assert r.json()["security_score"] == body["overall_score"]

    r = await client.get(
        "/api/v1/campaigns",
        headers={"Authorization": f"Bearer {access}"},
    )
    assert r.status_code == 200
    assert len(r.json()) >= 1

    cid = body["id"]
    r = await client.get(
        f"/api/v1/campaigns/{cid}/report",
        headers={"Authorization": f"Bearer {access}"},
    )
    assert r.status_code == 200
    assert r.json().get("engine") == "mock"

    r = await client.delete(
        f"/api/v1/campaigns/{cid}",
        headers={"Authorization": f"Bearer {access}"},
    )
    assert r.status_code == 204


@pytest.mark.asyncio
async def test_list_campaigns_filter_by_agent_id(client) -> None:
    email = f"cf_{uuid.uuid4().hex[:10]}@example.com"
    await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "longpassword1", "display_name": "C"},
    )
    access = (
        await client.post(
            "/api/v1/auth/login",
            json={"email": email, "password": "longpassword1"},
        )
    ).json()["access_token"]
    headers = {"Authorization": f"Bearer {access}"}
    graph = {
        "nodes": [{"id": "a", "type": "llm", "config": {"prompt": "x"}}],
        "edges": [],
        "entry_point": "a",
    }

    async def _mk_agent(name: str) -> str:
        r = await client.post(
            "/api/v1/agents",
            headers=headers,
            json={
                "name": name,
                "graph_definition": graph,
                "model_config": {"provider": "mock"},
            },
        )
        assert r.status_code == 201, r.text
        return r.json()["id"]

    a1 = await _mk_agent("A1")
    a2 = await _mk_agent("A2")

    r = await client.post(
        "/api/v1/campaigns",
        headers=headers,
        json={
            "agent_id": a1,
            "plugins": ["default"],
            "strategies": ["basic"],
            "run_async": False,
        },
    )
    assert r.status_code == 201, r.text

    r = await client.get("/api/v1/campaigns", headers=headers, params={"agent_id": a1})
    assert r.status_code == 200
    assert len(r.json()) == 1
    assert r.json()[0]["agent_id"] == a1

    r = await client.get("/api/v1/campaigns", headers=headers, params={"agent_id": a2})
    assert r.status_code == 200
    assert r.json() == []

    r = await client.get(
        "/api/v1/campaigns",
        headers=headers,
        params={"agent_id": str(uuid.uuid4())},
    )
    assert r.status_code == 404
