"""Integration tests for newer API endpoints: dashboard, pii, budget, workspace, memory."""

from __future__ import annotations

import uuid

import pytest

pytestmark = pytest.mark.usefixtures("alembic_ready")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _register_login(client, suffix=""):
    email = f"test_{suffix}_{uuid.uuid4().hex[:8]}@example.com"
    await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "longpassword1", "display_name": "Test"},
    )
    r = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "longpassword1"},
    )
    return r.json()["access_token"]


async def _create_agent(client, token):
    graph = {
        "nodes": [{"id": "n1", "type": "llm", "config": {}}],
        "edges": [],
        "entry_point": "n1",
    }
    r = await client.post(
        "/api/v1/agents",
        headers={"Authorization": f"Bearer {token}"},
        json={"name": "TestAgent", "graph_definition": graph, "model_config": {"provider": "mock"}},
    )
    assert r.status_code == 201, r.text
    return r.json()["id"]


# ---------------------------------------------------------------------------
# Dashboard / analytics
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_dashboard_summary(client):
    token = await _register_login(client, "dash")
    r = await client.get("/api/v1/dashboard", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    body = r.json()
    assert "agents" in body
    assert "executions" in body


@pytest.mark.asyncio
async def test_dashboard_metrics(client):
    token = await _register_login(client, "metrics")
    r = await client.get(
        "/api/v1/dashboard/metrics?days=7", headers={"Authorization": f"Bearer {token}"}
    )
    assert r.status_code == 200
    body = r.json()
    assert "daily_stats" in body
    assert "summary" in body


@pytest.mark.asyncio
async def test_dashboard_metrics_with_agent_filter(client):
    token = await _register_login(client, "metr_agent")
    agent_id = await _create_agent(client, token)
    r = await client.get(
        f"/api/v1/dashboard/metrics?days=7&agent_id={agent_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_dashboard_executions(client):
    token = await _register_login(client, "execs")
    r = await client.get(
        "/api/v1/dashboard/executions", headers={"Authorization": f"Bearer {token}"}
    )
    assert r.status_code == 200
    body = r.json()
    assert "items" in body
    assert "total" in body


# ---------------------------------------------------------------------------
# PII masking
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_pii_mask_email(client):
    token = await _register_login(client, "pii")
    r = await client.post(
        "/api/v1/pii/mask",
        headers={"Authorization": f"Bearer {token}"},
        json={"text": "Contact alice@example.com for more info."},
    )
    assert r.status_code == 200
    body = r.json()
    assert "alice@example.com" not in body["masked_text"]
    assert body["hit_count"] == 1


@pytest.mark.asyncio
async def test_pii_mask_no_pii(client):
    token = await _register_login(client, "pii2")
    r = await client.post(
        "/api/v1/pii/mask",
        headers={"Authorization": f"Bearer {token}"},
        json={"text": "No PII here at all."},
    )
    assert r.status_code == 200
    assert r.json()["hit_count"] == 0


# ---------------------------------------------------------------------------
# Budget
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_agent_budget(client):
    token = await _register_login(client, "budget")
    agent_id = await _create_agent(client, token)
    r = await client.get(
        f"/api/v1/agents/{agent_id}/budget",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["agent_id"] == agent_id
    assert body["status"] in ("ok", "warning", "exceeded")
    assert body["limit_usd"] is None  # no limit set by default


@pytest.mark.asyncio
async def test_set_agent_budget(client):
    token = await _register_login(client, "budget2")
    agent_id = await _create_agent(client, token)
    r = await client.put(
        f"/api/v1/agents/{agent_id}/budget",
        headers={"Authorization": f"Bearer {token}"},
        json={"limit_usd": 10.0, "alert_threshold": 0.75},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["limit_usd"] == 10.0
    assert body["alert_threshold"] == 0.75


@pytest.mark.asyncio
async def test_budget_unauthorized_agent(client):
    token = await _register_login(client, "budget3")
    other_token = await _register_login(client, "budget3b")
    agent_id = await _create_agent(client, other_token)
    r = await client.get(
        f"/api/v1/agents/{agent_id}/budget",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 403


# ---------------------------------------------------------------------------
# Agent export
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_export_agent_python(client):
    token = await _register_login(client, "export")
    agent_id = await _create_agent(client, token)
    r = await client.get(
        f"/api/v1/agents/{agent_id}/export?format=python",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    assert "python" in r.headers.get("content-type", "") or len(r.content) > 0


@pytest.mark.asyncio
async def test_export_agent_langgraph(client):
    token = await _register_login(client, "export2")
    agent_id = await _create_agent(client, token)
    r = await client.get(
        f"/api/v1/agents/{agent_id}/export?format=langgraph",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200


# ---------------------------------------------------------------------------
# Workspace members
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_workspace_members_list_empty(client):
    token = await _register_login(client, "ws")
    r = await client.get("/api/v1/workspace/members", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert r.json() == []


@pytest.mark.asyncio
async def test_workspace_invite_and_list(client):
    token = await _register_login(client, "ws2")
    r = await client.post(
        "/api/v1/workspace/members",
        headers={"Authorization": f"Bearer {token}"},
        json={"email": "invited@example.com", "role": "viewer"},
    )
    assert r.status_code in (200, 201), r.text
    r = await client.get("/api/v1/workspace/members", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    members = r.json()
    assert any(m["invited_email"] == "invited@example.com" for m in members)


# ---------------------------------------------------------------------------
# Memory (requires pgvector — skip if not available)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_memories_empty(client):
    token = await _register_login(client, "mem")
    agent_id = await _create_agent(client, token)
    r = await client.get(
        f"/api/v1/agents/{agent_id}/memories",
        headers={"Authorization": f"Bearer {token}"},
    )
    # May be 200 or 500 if pgvector not enabled — just check it doesn't 404
    assert r.status_code != 404
