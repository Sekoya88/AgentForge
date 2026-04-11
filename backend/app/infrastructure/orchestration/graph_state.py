"""LangGraph orchestration state shape and message helpers (extracted for clarity)."""

from typing import Annotated

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from langgraph.graph.message import add_messages
from typing_extensions import TypedDict

from app.domain.value_objects import MessageDict


class GraphState(TypedDict):
    """Graph state: messages + optional audio attachment."""

    messages: Annotated[list[BaseMessage], add_messages]
    audio_b64: str | None


def dicts_to_messages(items: list[MessageDict]) -> list[BaseMessage]:
    out: list[BaseMessage] = []
    for m in items:
        role = m.role
        content = m.content
        if role == "assistant":
            out.append(AIMessage(content=content))
        else:
            out.append(HumanMessage(content=content))
    return out


def messages_to_dicts(msgs: list[BaseMessage]) -> list[MessageDict]:
    from app.domain.message_content import coerce_message_content_to_str

    res: list[MessageDict] = []
    for i, m in enumerate(msgs):
        if isinstance(m, HumanMessage):
            res.append(
                MessageDict(
                    role="user",
                    content=coerce_message_content_to_str(m.content),
                )
            )
        elif isinstance(m, AIMessage):
            if m.additional_kwargs.get("_tool_result") and any(
                isinstance(msgs[j], AIMessage)
                and not (msgs[j].additional_kwargs or {}).get("_tool_result")
                for j in range(i + 1, len(msgs))
            ):
                continue
            res.append(
                MessageDict(
                    role="assistant",
                    content=coerce_message_content_to_str(m.content),
                )
            )
    return res


def message_tail_preview(msgs: list[BaseMessage], limit: int = 240) -> str:
    if not msgs:
        return ""
    last = msgs[-1]
    c = str(getattr(last, "content", "") or "")
    return c if len(c) <= limit else c[: limit - 3] + "..."


def last_ai_text(msgs: list[BaseMessage]) -> str:
    for m in reversed(msgs):
        if isinstance(m, AIMessage):
            return str(m.content or "")
    return ""


def lg_node_name(node_id: str) -> str:
    safe = "".join(c if c.isalnum() else "_" for c in node_id)
    return f"g_{safe}"
