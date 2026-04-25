import pytest
from langchain_core.messages import AIMessage
from agentforge import Agent

@pytest.mark.asyncio
@pytest.mark.integration
async def test_local_agent_llm(ollama_model):
    """
    Test a simple LocalAgent with a single LLM node using Ollama.
    Verifies that invoking the agent returns a valid AIMessage.
    """
    # Build a simple single-node agent
    agent_def = (
        Agent("TestBot")
        .model("ollama", ollama_model, temperature=0.0)
        .llm_node("chat", system_prompt="You are a helpful assistant. Reply with exactly one word: 'Hello'")
        .build()
    )
    from agentforge.agent import LocalAgent
    agent = LocalAgent(agent_def.model_dump())

    # Invoke the agent
    result = await agent.ainvoke({"input": "Say hello"})

    # Check the result
    assert "messages" in result
    messages = result["messages"]
    assert len(messages) > 0

    last_message = messages[-1]
    assert isinstance(last_message, AIMessage)
    assert "hello" in last_message.content.strip().lower()
