"""Agent template: interview-ops-assistant creates agent with attached skills.

When running this file alone, use: pytest … --cov-fail-under=0
(project addopts enforce 80% coverage on full runs).
"""

import uuid

import pytest

pytestmark = pytest.mark.usefixtures("alembic_ready")


@pytest.mark.asyncio
async def test_list_templates_includes_interview_ops(client) -> None:
    r = await client.get("/api/v1/templates")
    assert r.status_code == 200, r.text
    slugs = {x["slug"] for x in r.json()}
    assert "interview-ops-assistant" in slugs


@pytest.mark.asyncio
async def test_create_interview_ops_template_installs_skills(client) -> None:
    email = f"tpl_{uuid.uuid4().hex[:10]}@example.com"
    await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "longpassword1", "display_name": "T"},
    )
    login = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "longpassword1"},
    )
    access = login.json()["access_token"]
    headers = {"Authorization": f"Bearer {access}"}

    r = await client.post(
        "/api/v1/templates/interview-ops-assistant/create",
        headers=headers,
    )
    assert r.status_code == 201, r.text
    agent_id = r.json()["id"]

    r2 = await client.get(f"/api/v1/agents/{agent_id}", headers=headers)
    assert r2.status_code == 200, r2.text
    body = r2.json()
    assert len(body.get("skills", [])) >= 4
