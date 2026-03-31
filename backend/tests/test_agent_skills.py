import uuid

import pytest

pytestmark = pytest.mark.usefixtures("alembic_ready")


@pytest.mark.asyncio
async def test_agent_skills_attach_and_validate_flow(client) -> None:
    email = f"sk_{uuid.uuid4().hex[:10]}@example.com"
    r = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "longpassword1", "display_name": "S"},
    )
    assert r.status_code == 200, r.text
    login = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "longpassword1"},
    )
    access = login.json()["access_token"]
    headers = {"Authorization": f"Bearer {access}"}

    r = await client.post(
        "/api/v1/skills",
        headers=headers,
        json={
            "name": "echo_skill",
            "source_code": "def run(x: str) -> str:\n    return x\n",
            "parameters_schema": {"type": "object", "properties": {}, "required": []},
            "permissions": ["read"],
            "is_public": False,
        },
    )
    assert r.status_code == 201, r.text
    skill_id = r.json()["id"]

    r = await client.post(f"/api/v1/skills/{skill_id}/validate", headers=headers)
    assert r.status_code == 200, r.text
    assert r.json()["valid"] is True

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
        headers=headers,
        json={
            "name": "With skills",
            "graph_definition": graph,
            "model_config": {"provider": "mock"},
            "skills": [skill_id],
        },
    )
    assert r.status_code == 201, r.text
    agent_id = r.json()["id"]
    assert r.json()["skills"] == [skill_id]

    r = await client.put(
        f"/api/v1/agents/{agent_id}",
        headers=headers,
        json={"skills": []},
    )
    assert r.status_code == 200, r.text
    assert r.json()["skills"] == []

    bad = str(uuid.uuid4())
    r = await client.put(
        f"/api/v1/agents/{agent_id}",
        headers=headers,
        json={"skills": [bad]},
    )
    assert r.status_code == 422, r.text


@pytest.mark.asyncio
async def test_skill_validate_rejects_forbidden_import(client) -> None:
    email = f"sk2_{uuid.uuid4().hex[:10]}@example.com"
    await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "longpassword1", "display_name": "S"},
    )
    login = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "longpassword1"},
    )
    access = login.json()["access_token"]
    headers = {"Authorization": f"Bearer {access}"}

    r = await client.post(
        "/api/v1/skills",
        headers=headers,
        json={
            "name": "bad_skill",
            "source_code": "import os\ndef run():\n    pass\n",
            "parameters_schema": {"type": "object", "properties": {}, "required": []},
            "permissions": ["read"],
            "is_public": False,
        },
    )
    assert r.status_code == 201, r.text
    skill_id = r.json()["id"]

    r = await client.post(f"/api/v1/skills/{skill_id}/validate", headers=headers)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["valid"] is False
    assert "import" in body["message"].lower() or "not allowed" in body["message"].lower()


@pytest.mark.asyncio
async def test_tool_node_executes_attached_skill_by_name(client) -> None:
    email = f"sk3_{uuid.uuid4().hex[:10]}@example.com"
    await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "longpassword1", "display_name": "S"},
    )
    login = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "longpassword1"},
    )
    access = login.json()["access_token"]
    headers = {"Authorization": f"Bearer {access}"}

    r = await client.post(
        "/api/v1/skills",
        headers=headers,
        json={
            "name": "upper_skill",
            "source_code": "def run(x: str) -> str:\n    return x.upper()\n",
            "parameters_schema": {"type": "object", "properties": {}, "required": []},
            "permissions": ["read"],
            "is_public": False,
        },
    )
    assert r.status_code == 201, r.text
    skill_id = r.json()["id"]

    graph = {
        "nodes": [
            {"id": "t1", "type": "tool", "config": {"tool_name": "upper_skill"}},
        ],
        "edges": [],
        "entry_point": "t1",
    }
    r = await client.post(
        "/api/v1/agents",
        headers=headers,
        json={
            "name": "Skill runner",
            "graph_definition": graph,
            "model_config": {"provider": "mock"},
            "skills": [skill_id],
        },
    )
    assert r.status_code == 201, r.text
    agent_id = r.json()["id"]

    r = await client.post(
        f"/api/v1/agents/{agent_id}/execute",
        headers=headers,
        json={"input_messages": [{"role": "user", "content": "hello"}]},
    )
    assert r.status_code == 200, r.text
    msgs = r.json()["output_messages"]
    assert msgs
    joined = " ".join(str(m.get("content", "")) for m in msgs)
    assert "HELLO" in joined


@pytest.mark.asyncio
async def test_public_skill_registry_no_auth(client) -> None:
    email = f"reg_{uuid.uuid4().hex[:10]}@example.com"
    await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "longpassword1", "display_name": "Registry Author"},
    )
    access = (
        await client.post(
            "/api/v1/auth/login",
            json={"email": email, "password": "longpassword1"},
        )
    ).json()["access_token"]
    headers = {"Authorization": f"Bearer {access}"}

    r = await client.post(
        "/api/v1/skills",
        headers=headers,
        json={
            "name": "public_echo_registry",
            "description": "registry search token xyzabc",
            "source_code": "def run(x: str) -> str:\n    return x\n",
            "parameters_schema": {"type": "object", "properties": {}, "required": []},
            "is_public": False,
        },
    )
    assert r.status_code == 201, r.text
    skill_id = r.json()["id"]

    # Registry endpoint should be accessible without auth
    r = await client.get("/api/v1/skills/registry")
    assert r.status_code == 200, r.text
    items = r.json()
    assert isinstance(items, list)
    # Skill is private (is_public=False), so it should NOT appear in the registry
    assert not any(x.get("name") == "public_echo_registry" for x in items)

    # Search should also not return a private skill
    r = await client.get("/api/v1/skills/registry", params={"search": "xyzabc"})
    assert r.status_code == 200
    filtered = r.json()
    assert not any(x.get("name") == "public_echo_registry" for x in filtered)

    # Owner can delete their own private skill
    r = await client.delete(f"/api/v1/skills/{skill_id}", headers=headers)
    assert r.status_code == 204
