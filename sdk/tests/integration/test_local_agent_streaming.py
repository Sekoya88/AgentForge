import pytest
from langchain_core.messages import AIMessage
from agentforge import Agent

@pytest.mark.asyncio
@pytest.mark.integration
async def test_local_agent_streaming(ollama_model):
    """
    Test streaming functionality of a LocalAgent with an Ollama LLM node.
    Verifies that calling astream() yields at least one event with messages.
    """
    agent_def = (
        Agent("StreamBot")
        .model("ollama", ollama_model, temperature=0.7)
        .llm_node("chat", system_prompt="You are a helpful assistant.")
        .build()
    )
    from agentforge.agent import LocalAgent
    agent = LocalAgent(agent_def.model_dump())

    events = []
    # Count the number of events yielded during stream
    async for event in agent.astream({"input": "Tell me a short story."}):
        events.append(event)

    assert len(events) > 0, "astream() should yield at least one event"

    # Check that at least one event updates the messages state
    has_message_event = False
    for event in events:
        # LangGraph typically yields dicts with the node name as key, e.g. {"chat": {"messages": [...]}}
        for node_name, node_state in event.items():
            if "messages" in node_state:
                has_message_event = True
                messages = node_state["messages"]
                assert len(messages) > 0
                assert isinstance(messages[-1], AIMessage)
                assert messages[-1].content

    assert has_message_event, "At least one event should contain message updates"
