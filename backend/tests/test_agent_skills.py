import uuid

import pytest

from app.domain.default_agents import _DEFAULT_AGENTS
from app.domain.skill_templates import SKILL_TEMPLATES

pytestmark = pytest.mark.usefixtures("alembic_ready")


def test_default_agent_skill_templates_exist() -> None:
    names = {t["name"] for t in SKILL_TEMPLATES}
    for agent in _DEFAULT_AGENTS:
        for skill in agent["skills"]:
            assert skill in names, f"missing template {skill!r} for agent {agent['name']!r}"


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


@pytest.mark.asyncio
async def test_seed_default_skills_idempotent(client) -> None:
    email = f"seed_{uuid.uuid4().hex[:10]}@example.com"
    await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "longpassword1", "display_name": "Seed"},
    )
    login = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "longpassword1"},
    )
    access = login.json()["access_token"]
    headers = {"Authorization": f"Bearer {access}"}

    r1 = await client.post("/api/v1/skills/seed-defaults", headers=headers)
    assert r1.status_code == 201, r1.text
    body1 = r1.json()
    assert "count" in body1
    assert body1["count"] >= 0
    assert "created" in body1

    r2 = await client.post("/api/v1/skills/seed-defaults", headers=headers)
    assert r2.status_code == 201, r2.text
    body2 = r2.json()
    assert body2["count"] == 0
    assert body2["created"] == []


@pytest.mark.asyncio
async def test_seed_defaults_creates_default_agents(client) -> None:
    """First POST to seed-defaults must create at least one default skill."""
    email = f"sd1_{uuid.uuid4().hex[:10]}@example.com"
    await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "longpassword1", "display_name": "SD1"},
    )
    login = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "longpassword1"},
    )
    access = login.json()["access_token"]
    headers = {"Authorization": f"Bearer {access}"}

    r = await client.post("/api/v1/skills/seed-defaults", headers=headers)
    assert r.status_code == 201, r.text
    body = r.json()
    assert "count" in body
    assert "created" in body
    # A fresh user should get at least one skill created from the default templates
    assert body["count"] > 0
    assert len(body["created"]) > 0


@pytest.mark.asyncio
async def test_seed_defaults_is_idempotent(client) -> None:
    """POSTing seed-defaults twice must not fail; second call returns count=0."""
    email = f"sd2_{uuid.uuid4().hex[:10]}@example.com"
    await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "longpassword1", "display_name": "SD2"},
    )
    login = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "longpassword1"},
    )
    access = login.json()["access_token"]
    headers = {"Authorization": f"Bearer {access}"}

    r1 = await client.post("/api/v1/skills/seed-defaults", headers=headers)
    assert r1.status_code == 201, r1.text

    # Second call must succeed without errors
    r2 = await client.post("/api/v1/skills/seed-defaults", headers=headers)
    assert r2.status_code == 201, r2.text
    body2 = r2.json()
    assert body2["count"] == 0
    assert body2["created"] == []


@pytest.mark.asyncio
async def test_import_bundle_invalid_json_returns_422(client) -> None:
    """Posting a bundle with a wrong type for 'agent' (not a dict) must return 422."""
    email = f"ib1_{uuid.uuid4().hex[:10]}@example.com"
    await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "longpassword1", "display_name": "IB1"},
    )
    login = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "longpassword1"},
    )
    access = login.json()["access_token"]
    headers = {"Authorization": f"Bearer {access}"}

    # 'agent' must be a dict; sending a string triggers Pydantic validation failure → 422
    r = await client.post(
        "/api/v1/agents/import-bundle",
        headers=headers,
        json={"agentforge_version": "2.0", "agent": "not-a-dict"},
    )
    assert r.status_code == 422, r.text


@pytest.mark.asyncio
async def test_import_bundle_missing_required_fields_returns_422(client) -> None:
    """Bundle without required 'agentforge_version' field must return 422."""
    email = f"ib2_{uuid.uuid4().hex[:10]}@example.com"
    await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "longpassword1", "display_name": "IB2"},
    )
    login = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "longpassword1"},
    )
    access = login.json()["access_token"]
    headers = {"Authorization": f"Bearer {access}"}

    # Missing agentforge_version (required by Pydantic) → 422
    r = await client.post(
        "/api/v1/agents/import-bundle",
        headers=headers,
        json={"agent": {"name": "Test"}},
    )
    assert r.status_code == 422, r.text


@pytest.mark.asyncio
async def test_import_bundle_rejects_invalid_agent_payload(client) -> None:
    email = f"imp_{uuid.uuid4().hex[:10]}@example.com"
    await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "longpassword1", "display_name": "Imp"},
    )
    login = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "longpassword1"},
    )
    access = login.json()["access_token"]
    headers = {"Authorization": f"Bearer {access}"}

    r = await client.post(
        "/api/v1/agents/import-bundle",
        headers=headers,
        json={"agentforge_version": "2.0", "agent": {}},
    )
    assert r.status_code == 400, r.text
    assert "name" in r.json()["detail"].lower()
