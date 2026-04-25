import json
from typing import AsyncGenerator, Any

from langchain_core.messages import BaseMessage, AIMessage

async def format_agent_stream(agent: Any, input_dict: dict[str, Any]) -> AsyncGenerator[str, None]:
    """
    Consumes an agent's astream events and yields formatted string events.
    Useful for streaming to the console or wrapping in Server-Sent Events (SSE).
    """
    try:
        async for event in agent._compiled_graph.astream_events(input_dict, version="v2"):
            kind = event["event"]
            if kind == "on_chat_model_stream":
                content = event["data"]["chunk"].content
                if content:
                    yield json.dumps({"type": "token", "content": content}) + "\n"
            elif kind == "on_chat_model_end":
                message = event["data"]["output"]
                if isinstance(message, dict) and "message" in message:
                    message = message["message"]
                if hasattr(message, "content"):
                    yield json.dumps({"type": "node_end", "node": event.get("name", "unknown"), "content": message.content}) + "\n"
            elif kind == "on_tool_start":
                yield json.dumps({"type": "tool_start", "tool": event.get("name")}) + "\n"
            elif kind == "on_tool_end":
                yield json.dumps({"type": "tool_end", "tool": event.get("name")}) + "\n"
    except Exception as e:
        yield json.dumps({"type": "error", "message": str(e)}) + "\n"

async def astream_events(agent: Any, input_dict: dict[str, Any]) -> AsyncGenerator[dict[str, Any], None]:
    """
    Yields parsed events.
    """
    async for event in agent._compiled_graph.astream_events(input_dict, version="v2"):
        yield event
