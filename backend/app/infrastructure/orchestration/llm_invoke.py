"""Chat completions for graph `llm` nodes (OpenAI / Google Gemini / Fine-tuned)."""

import os
from typing import Any

import httpx
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage

from app.config import get_settings


def _get_langfuse_callbacks(settings):
    if settings.langfuse_public_key and settings.langfuse_secret_key:
        os.environ.setdefault("LANGFUSE_PUBLIC_KEY", settings.langfuse_public_key)
        os.environ.setdefault("LANGFUSE_SECRET_KEY", settings.langfuse_secret_key)
        if settings.langfuse_host:
            os.environ.setdefault("LANGFUSE_HOST", settings.langfuse_host)

        try:
            from langfuse.langchain import CallbackHandler

            return [CallbackHandler()]
        except ImportError:
            return []
    return []


def _echo_stub(system_prompt: str, user_text: str) -> str:
    body = f"{system_prompt}\n\n{user_text}".strip() if system_prompt else user_text
    if not body:
        body = "(empty)"
    return f"Echo: {body}"


def _last_user_text(messages: list[BaseMessage]) -> str:
    for m in reversed(messages):
        if isinstance(m, HumanMessage):
            return str(m.content or "")
    return ""


async def _invoke_finetuned(
    prior_messages: list[BaseMessage],
    *,
    system_prompt: str,
    model_config: dict[str, Any],
) -> str:
    """Call the Modal inference endpoint for a fine-tuned model."""
    settings = get_settings()
    endpoint = getattr(settings, "modal_inference_url", None)
    if not endpoint:
        raise RuntimeError(
            "MODAL_INFERENCE_URL not set. Deploy inference.py first: "
            "`cd backend && modal deploy modal_functions/inference.py`"
        )

    job_id = model_config.get("finetune_job_id")
    if not job_id:
        raise RuntimeError(
            "finetune_job_id is required in model_config when provider is 'finetuned'"
        )

    # Build prompt from messages
    parts: list[str] = []
    if system_prompt.strip():
        parts.append(f"System: {system_prompt.strip()}")
    for msg in prior_messages:
        if isinstance(msg, HumanMessage):
            parts.append(f"User: {msg.content}")
        elif isinstance(msg, AIMessage):
            parts.append(f"Assistant: {msg.content}")
        elif isinstance(msg, SystemMessage):
            parts.append(f"System: {msg.content}")
    parts.append("Assistant:")
    prompt = "\n".join(parts)

    temperature = model_config.get("temperature")
    if temperature is None:
        temperature = 0.7

    async with httpx.AsyncClient(timeout=120) as client:
        resp = await client.post(
            endpoint,
            json={
                "job_id": job_id,
                "prompt": prompt,
                "max_new_tokens": 256,
                "temperature": float(temperature),
            },
        )
        resp.raise_for_status()
        data = resp.json()

    if "error" in data:
        raise RuntimeError(f"Inference error: {data['error']}")

    return str(data.get("response", ""))


async def invoke_chat_llm(
    prior_messages: list[BaseMessage],
    *,
    system_prompt: str,
    model_config: dict[str, Any],
    openai_api_key: str | None,
    google_api_key: str | None,
) -> str:
    """
    Returns assistant text. `provider` in model_config: mock | openai | google | gemini.
    """
    provider = str(model_config.get("provider") or "mock").lower()
    if provider in ("mock", "echo", "none", ""):
        return _echo_stub(system_prompt, _last_user_text(prior_messages))

    temperature = model_config.get("temperature")
    if temperature is None:
        temperature = 0.2
    else:
        temperature = float(temperature)

    lc_messages: list[BaseMessage] = []
    if system_prompt.strip():
        lc_messages.append(SystemMessage(content=system_prompt.strip()))
    lc_messages.extend(prior_messages)

    settings = get_settings()
    callbacks = _get_langfuse_callbacks(settings)

    if provider == "openai":
        if not openai_api_key:
            raise RuntimeError("OPENAI_API_KEY is required when model_config.provider is 'openai'")
        model_name = str(model_config.get("model") or "gpt-5.4-mini")
        from langchain_openai import ChatOpenAI

        llm = ChatOpenAI(
            model=model_name,
            api_key=openai_api_key,
            temperature=temperature,
        )
        out = await llm.ainvoke(lc_messages, config={"callbacks": callbacks})
        if isinstance(out, AIMessage):
            return str(out.content or "")
        return str(getattr(out, "content", "") or out)

    if provider in ("google", "gemini"):
        if not google_api_key:
            raise RuntimeError(
                "GOOGLE_API_KEY is required when model_config.provider is 'google' or 'gemini'",
            )
        model_name = str(model_config.get("model") or "gemini-2.5-pro")
        from langchain_google_genai import ChatGoogleGenerativeAI

        llm = ChatGoogleGenerativeAI(
            model=model_name,
            google_api_key=google_api_key,
            temperature=temperature,
        )
        out = await llm.ainvoke(lc_messages, config={"callbacks": callbacks})
        if isinstance(out, AIMessage):
            return str(out.content or "")
        return str(getattr(out, "content", "") or out)

    if provider == "finetuned":
        return await _invoke_finetuned(
            prior_messages, system_prompt=system_prompt, model_config=model_config
        )

    raise ValueError(
        f"Unknown model_config.provider: {provider!r} "
        "(use mock, openai, google, gemini, or finetuned)",
    )
