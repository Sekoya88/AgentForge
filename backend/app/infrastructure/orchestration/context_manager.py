import logging
from typing import Any

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage

from app.domain.execution_policy import ExecutionPolicyValidated

logger = logging.getLogger(__name__)


async def compress_context(
    messages: list[BaseMessage], invoke_chat_llm, model_config: dict[str, Any], settings: Any
) -> list[BaseMessage]:
    """Compress older messages into a summary while keeping recent ones."""
    if len(messages) <= 3:
        return messages

    # We want to keep the system prompt if any
    sys_msgs = [m for m in messages if isinstance(m, SystemMessage)]
    # Keep the last 2 messages intact
    recent_msgs = messages[-2:]
    # Summarize the rest
    msgs_to_compress = [m for m in messages if m not in sys_msgs and m not in recent_msgs]

    if not msgs_to_compress:
        return messages

    # Format for summarization
    conversation = "\n".join(
        [
            f"{'User' if isinstance(m, HumanMessage) else 'Assistant'}: {m.content}"
            for m in msgs_to_compress
        ]
    )

    prompt = (
        "Summarize the following conversation history concisely. "
        "Keep all important facts, entities, constraints, and tool outputs. "
        "Focus on what is needed to continue the conversation.\n\n"
        f"{conversation}"
    )

    try:
        summary_text, _ = await invoke_chat_llm(
            prior_messages=[HumanMessage(content=prompt)],
            system_prompt=(
                "You are a context compression assistant. "
                "Provide a dense summary of the conversation."
            ),
            model_config=model_config,
            openai_api_key=settings.openai_api_key,
            google_api_key=settings.google_api_key,
            anthropic_api_key=settings.anthropic_api_key,
        )

        summary_msg = AIMessage(content=f"[Conversation Summary] {summary_text}")
        return sys_msgs + [summary_msg] + recent_msgs
    except Exception as e:
        logger.warning(f"Context compression failed: {e}")
        # On failure, just return original messages to avoid losing data
        return messages


async def apply_context_policy(
    messages: list[BaseMessage],
    policy: ExecutionPolicyValidated | None,
    invoke_chat_llm,
    model_config: dict[str, Any],
    settings: Any,
    current_tokens: int = 0,
) -> list[BaseMessage]:
    """Apply sliding window and token compression based on policy."""
    if not policy:
        return messages

    new_messages = messages

    # 1. Sliding Window (max_message_history)
    if policy.max_message_history and policy.max_message_history > 0:
        # Keep system messages
        sys_msgs = [m for m in new_messages if isinstance(m, SystemMessage)]
        other_msgs = [m for m in new_messages if not isinstance(m, SystemMessage)]
        if len(other_msgs) > policy.max_message_history:
            new_messages = sys_msgs + other_msgs[-policy.max_message_history :]

    # 2. Compression (context_compression_threshold)
    if (
        policy.context_compression_threshold
        and current_tokens > policy.context_compression_threshold
    ):
        new_messages = await compress_context(new_messages, invoke_chat_llm, model_config, settings)

    return new_messages
