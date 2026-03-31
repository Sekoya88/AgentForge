import pytest
from langchain_core.messages import AIMessage
from agentforge import Agent

@pytest.mark.asyncio
@pytest.mark.integration
async def test_local_agent_conditional(ollama_model):
    """
    Test a LocalAgent with conditional edges.
    Verifies that the agent routes correctly based on the LLM's response using the 'contains' condition.
    """
    # Create an agent that routes to different nodes based on the LLM's response
    # It starts at the categorizer node.
    # If it says 'red', it goes to 'red_node', if 'blue', it goes to 'blue_node'.
    agent_def = (
        Agent("ColorRouter")
        .model("ollama", ollama_model, temperature=0.0)
        .llm_node("categorizer", system_prompt="You are a color classifier. Reply with exactly one word: either 'RED' or 'BLUE'. The user will give you a hint.")
        .llm_node("red_node", system_prompt="You are the red node. Reply 'I received red'.")
        .llm_node("blue_node", system_prompt="You are the blue node. Reply 'I received blue'.")
        .edge("categorizer", "red_node", condition="RED", condition_type="contains")
        .edge("categorizer", "blue_node", condition="BLUE", condition_type="contains")
        .build()
    )
    from agentforge.agent import LocalAgent
    agent = LocalAgent(agent_def.model_dump())

    # Test path RED
    res_red = await agent.ainvoke({"input": "The color of blood"})
    msgs_red = res_red.get("messages", [])
    assert len(msgs_red) >= 3 # Human (input), AIMessage (RED), AIMessage (I received red)
    assert any("I received red" in str(m.content) for m in msgs_red)
    assert not any("I received blue" in str(m.content) for m in msgs_red)

    # Test path BLUE
    res_blue = await agent.ainvoke({"input": "The color of the sky"})
    msgs_blue = res_blue.get("messages", [])
    assert len(msgs_blue) >= 3
    assert any("I received blue" in str(m.content) for m in msgs_blue)
    assert not any("I received red" in str(m.content) for m in msgs_blue)
