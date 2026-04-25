import pytest
from langchain_core.messages import AIMessage
from agentforge import Agent

@pytest.mark.asyncio
@pytest.mark.integration
async def test_local_agent_tool(ollama_model):
    """
    Test a LocalAgent with a tool node and an LLM node interacting.
    Verifies that the LLM node can be followed by a tool node and the tool's result
    is injected into the state.
    """
    code = (
        "def run(text: str) -> str:\n"
        "    return 'SECRET_WORD'\n"
    )

    agent_def = (
        Agent("ToolBot")
        .model("ollama", ollama_model, temperature=0.0)
        .skill("get_secret", skill_type="code", source_code=code)
        .tool_node("fetch_secret", tool_name="get_secret")
        .llm_node("chat", system_prompt="You summarize the tool's response.")
        .edge("fetch_secret", "chat")
        .build()
    )
    from agentforge.agent import LocalAgent
    agent = LocalAgent(agent_def.model_dump())

    # We start the graph at the tool node
    # Since we didn't specify an entry point, builder defaults to the first node ("fetch_secret")
    result = await agent.ainvoke({"input": "What is the secret?"})

    messages = result.get("messages", [])
    assert len(messages) >= 2

    # The first message in the result after input should be the tool's output
    # (Since tool node appends an AIMessage with the result)
    tool_msg = next((m for m in messages if isinstance(m, AIMessage) and "Tool 'get_secret' result" in str(m.content)), None)
    assert tool_msg is not None
    assert "SECRET_WORD" in tool_msg.content

    # The last message should be the LLM's response
    last_msg = messages[-1]
    assert isinstance(last_msg, AIMessage)
    # The LLM should have seen the tool output and ideally mentions the secret
    # Since Ollama models might respond differently, we just ensure it's an AIMessage
    assert last_msg.content.strip() != ""
