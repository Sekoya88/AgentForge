import os
import json
import pytest
import tempfile
from langchain_core.messages import AIMessage
from agentforge import Agent, AgentPolicy, load_agent

@pytest.mark.asyncio
@pytest.mark.integration
async def test_builder_export_reload(ollama_model):
    """
    Test the full round-trip of an Agent: build -> export to JSON -> load_agent -> invoke.
    """
    policy = AgentPolicy().max_cost(1.0)

    agent_def = (
        Agent("ExportBot")
        .model("ollama", ollama_model, temperature=0.0)
        .policy(policy)
        .llm_node("chat", system_prompt="You are an exported bot. Reply 'exported'.")
        .build()
    )

    payload = agent_def.model_dump(mode="json", by_alias=True)

    with tempfile.TemporaryDirectory() as tmpdir:
        json_path = os.path.join(tmpdir, "agent.json")
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(payload, f)

        # Reload
        reloaded_agent = load_agent(json_path)

        # Verify basic attributes
        assert reloaded_agent.name == "ExportBot"
        assert reloaded_agent.model_config.get("provider") == "ollama"
        assert reloaded_agent.model_config.get("model") == ollama_model

        # Policy is preserved
        assert reloaded_agent.execution_policy is not None
        assert reloaded_agent.execution_policy.get("max_cost_usd") == 1.0

        # Invoke the reloaded agent
        res = await reloaded_agent.ainvoke({"input": "Are you loaded?"})

        messages = res.get("messages", [])
        assert len(messages) >= 2
        last_msg = messages[-1]
        assert isinstance(last_msg, AIMessage)
        # Content verification may vary based on Ollama model, but the node runs correctly
        assert last_msg.content.strip() != ""
