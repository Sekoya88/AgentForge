import pytest
from langchain_core.messages import AIMessage
from agentforge import Agent
from agentforge.agent import node

@node("my_echo_plugin")
async def echo_plugin_node(state, config):
    """Custom node: LocalAgent calls plugins as (state, config)."""
    last_message = state["messages"][-1].content
    return {"messages": [AIMessage(content=f"ECHO: {last_message}")]}

@pytest.mark.asyncio
@pytest.mark.integration
async def test_local_agent_custom_node(ollama_model):
    """
    Test a LocalAgent with a custom node plugin.
    Verifies that the @node decorator registers the custom node and it is executed correctly.
    """
    agent_def = (
        Agent("CustomNodeBot")
        .model("ollama", ollama_model, temperature=0.0)
        # Add the custom node with type "my_echo_plugin"
        .custom_node("echo_step", node_type="my_echo_plugin", config={})
        .llm_node("chat", system_prompt="You summarize what was echoed.")
        .edge("echo_step", "chat")
        .build()
    )
    from agentforge.agent import LocalAgent
    agent = LocalAgent(agent_def.model_dump())

    result = await agent.ainvoke({"input": "Hello World!"})

    messages = result.get("messages", [])
    assert len(messages) >= 2

    # We expect the custom node to have processed the input
    echo_msg = next((m for m in messages if isinstance(m, AIMessage) and m.content.startswith("ECHO:")), None)
    assert echo_msg is not None
    assert "Hello World!" in echo_msg.content

    # Check that LLM also ran
    last_msg = messages[-1]
    assert isinstance(last_msg, AIMessage)
    assert last_msg.content.strip() != ""
