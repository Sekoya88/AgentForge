import uuid

import pytest

pytestmark = pytest.mark.usefixtures("alembic_ready")


@pytest.mark.asyncio
async def test_register_login_me_and_agent_crud(client) -> None:
    email = f"e2e_{uuid.uuid4().hex[:10]}@example.com"
    r = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "longpassword1", "display_name": "E2E"},
    )
    assert r.status_code == 200, r.text
    user_id = r.json()["id"]

    r = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "longpassword1"},
    )
    assert r.status_code == 200, r.text
    access = r.json()["access_token"]

    r = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {access}"},
    )
    assert r.status_code == 200
    assert r.json()["id"] == user_id

    graph = {
        "nodes": [
            {"id": "a", "type": "llm", "config": {"prompt": "You are a tester."}},
            {"id": "b", "type": "tool", "config": {"tool_name": "echo"}},
        ],
        "edges": [{"from": "a", "to": "b"}],
        "entry_point": "a",
    }
    r = await client.post(
        "/api/v1/agents",
        headers={"Authorization": f"Bearer {access}"},
        json={
            "name": "Demo",
            "description": "d",
            "graph_definition": graph,
            "model_config": {"provider": "mock"},
        },
    )
    assert r.status_code == 201, r.text
    agent_id = r.json()["id"]

    r = await client.post(
        f"/api/v1/agents/{agent_id}/execute",
        headers={"Authorization": f"Bearer {access}"},
        json={"input_messages": [{"role": "user", "content": "hi"}]},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "completed"
    assert body["output_messages"]

    r = await client.get(
        f"/api/v1/agents/{agent_id}/executions",
        headers={"Authorization": f"Bearer {access}"},
    )
    assert r.status_code == 200
    assert len(r.json()) >= 1
