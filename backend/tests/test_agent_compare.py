"""Agent A/B compare: POST /agents/{id}/compare."""

import uuid

import pytest

pytestmark = pytest.mark.usefixtures("alembic_ready")


@pytest.mark.asyncio
async def test_compare_two_variants_sync_mock_agent(client) -> None:
    email = f"cmp_{uuid.uuid4().hex[:10]}@example.com"
    await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "longpassword1", "display_name": "C"},
    )
    login = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "longpassword1"},
    )
    access = login.json()["access_token"]
    headers = {"Authorization": f"Bearer {access}"}

    graph = {
        "nodes": [
            {"id": "llm", "type": "llm", "config": {"prompt": "You are a tester."}},
        ],
        "edges": [],
        "entry_point": "llm",
    }
    r = await client.post(
        "/api/v1/agents",
        headers=headers,
        json={
            "name": "CompareMe",
            "graph_definition": graph,
            "model_config": {"provider": "mock", "model": "mock", "temperature": 0.5},
        },
    )
    assert r.status_code == 201, r.text
    agent_id = r.json()["id"]

    r = await client.post(
        f"/api/v1/agents/{agent_id}/compare",
        headers=headers,
        json={
            "message": "Say hello in one word.",
            "run_async": False,
            "variants": [
                {"label": "cold", "model_config_override": {"temperature": 0.1}},
                {"label": "hot", "model_config_override": {"temperature": 0.9}},
            ],
        },
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert "compare_group_id" in body
    gid = body["compare_group_id"]
    exes = body["executions"]
    assert len(exes) == 2
    assert exes[0]["compare_group_id"] == gid
    assert exes[1]["compare_group_id"] == gid
    assert exes[0]["compare_label"] == "cold"
    assert exes[1]["compare_label"] == "hot"
    assert exes[0]["status"] == "completed"
    assert exes[1]["status"] == "completed"
