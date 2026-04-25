import pytest
from langchain_core.messages import AIMessage
from agentforge import Agent, AgentPolicy
from langgraph.errors import GraphRecursionError

@pytest.mark.asyncio
@pytest.mark.integration
async def test_local_agent_policy(ollama_model):
    """
    Test a LocalAgent with a policy that sets max_graph_steps=1.
    Verifies that the graph execution stops after 1 step.
    """
    # Create an agent with an infinite loop
    policy = AgentPolicy().max_steps(1)

    agent_def = (
        Agent("PolicyBot")
        .model("ollama", ollama_model, temperature=0.0)
        .policy(policy)
        .llm_node("loop_node", system_prompt="You are in a loop. Say 'hello'")
        .edge("loop_node", "loop_node") # infinite loop
        .build()
    )
    from agentforge.agent import LocalAgent
    agent = LocalAgent(agent_def.model_dump())

    # Invoking this agent should raise GraphRecursionError because max_steps=1
    with pytest.raises(GraphRecursionError):
        await agent.ainvoke({"input": "Start"})

    # But we can also check that it passes successfully if the policy is not overly restrictive
    policy2 = AgentPolicy().max_steps(5)

    agent2_def = (
        Agent("PolicyBot2")
        .model("ollama", ollama_model, temperature=0.0)
        .policy(policy2)
        .llm_node("single_node", system_prompt="You are a normal bot. Say 'hello'")
        .build()
    )
    agent2 = LocalAgent(agent2_def.model_dump())

    # Should work fine
    res = await agent2.ainvoke({"input": "Hi"})
    messages = res.get("messages", [])
    assert len(messages) >= 2
    assert isinstance(messages[-1], AIMessage)
