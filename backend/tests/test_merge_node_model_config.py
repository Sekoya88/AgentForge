"""Unit tests for LLM node model_config merge (agent defaults vs node overrides)."""

from app.infrastructure.orchestration.langgraph_orchestrator import _merge_node_model_config


def test_merge_preserves_agent_temperature_when_node_omits() -> None:
    agent = {"provider": "openai", "model": "gpt-5.4-mini", "temperature": 0.3}
    node: dict = {"prompt": "hi"}
    merged = _merge_node_model_config(agent, node)
    assert merged["temperature"] == 0.3
    assert merged["model"] == "gpt-5.4-mini"


def test_merge_node_temperature_overrides_agent() -> None:
    agent = {"provider": "openai", "temperature": 0.3}
    node = {"temperature": 0.9}
    merged = _merge_node_model_config(agent, node)
    assert merged["temperature"] == 0.9


def test_merge_node_model_overrides_agent() -> None:
    agent = {"provider": "google", "model": "gemini-2.5-flash"}
    node = {"model": "gemini-2.5-pro"}
    merged = _merge_node_model_config(agent, node)
    assert merged["model"] == "gemini-2.5-pro"
