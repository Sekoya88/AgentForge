"""Tests for AgentForge SDK client."""
import pytest
import respx
import httpx
from agentforge_sdk import AgentForgeClient


BASE_URL = "http://test.agentforge.com"


@pytest.fixture
def client():
    return AgentForgeClient(base_url=BASE_URL, api_key="test-key")


def test_client_initialization(client):
    assert client.base_url == BASE_URL


@respx.mock
def test_run_agent_success(client):
    respx.post(f"{BASE_URL}/api/v1/agents/agent-1/execute").mock(
        return_value=httpx.Response(200, json={
            "id": "exec-1",
            "status": "completed",
            "output_messages": [{"role": "assistant", "content": "Hello!"}],
            "token_usage": {"total_tokens": 10},
            "duration_ms": 500,
        })
    )
    result = client.agents.run(agent_id="agent-1", message="Hi")
    assert result.status == "completed"
    assert result.output == "Hello!"


@respx.mock
def test_list_agents(client):
    respx.get(f"{BASE_URL}/api/v1/agents").mock(
        return_value=httpx.Response(200, json=[
            {"id": "agent-1", "name": "Test Agent", "description": "A test", "status": "live"}
        ])
    )
    agents = client.agents.list()
    assert len(agents) == 1
    assert agents[0].name == "Test Agent"


@respx.mock
def test_create_conversation(client):
    respx.post(f"{BASE_URL}/api/v1/agents/agent-1/conversations").mock(
        return_value=httpx.Response(201, json={
            "id": "conv-1", "agent_id": "agent-1", "thread_id": "thread-123",
            "title": None, "message_count": 0
        })
    )
    conv = client.conversations.create(agent_id="agent-1")
    assert conv.thread_id == "thread-123"


def test_context_manager():
    with AgentForgeClient(base_url=BASE_URL, api_key="test") as c:
        assert c.base_url == BASE_URL
    # Should not raise after __exit__
