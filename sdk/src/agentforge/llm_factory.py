"""Lightweight LLM factory for the AgentForge SDK (no backend infra dependencies)."""

from typing import Any

try:
    from langchain_openai import ChatOpenAI
except ImportError:  # pragma: no cover
    ChatOpenAI = None  # type: ignore[assignment,misc]

try:
    from langchain_google_genai import ChatGoogleGenerativeAI
except ImportError:  # pragma: no cover
    ChatGoogleGenerativeAI = None  # type: ignore[assignment,misc]

try:
    from langchain_ollama import ChatOllama
except ImportError:  # pragma: no cover
    ChatOllama = None  # type: ignore[assignment,misc]


def build_llm(
    provider: str,
    model: str,
    temperature: float = 0.7,
    base_url: str | None = None,
    options: dict[str, Any] | None = None,
):
    """Return an instantiated LangChain chat model for the given provider.

    Raises ValueError for unknown providers.
    No network call is made at construction time.
    """
    provider = provider.lower()

    if provider == "openai":
        return ChatOpenAI(model=model, temperature=temperature)

    if provider in ("google", "gemini"):
        return ChatGoogleGenerativeAI(model=model, temperature=temperature)

    if provider == "ollama":
        kwargs: dict[str, Any] = {
            "model": model,
            "temperature": temperature,
            "base_url": base_url or "http://localhost:11434",
        }
        if options:
            kwargs.update(options)
        return ChatOllama(**kwargs)

    raise ValueError(
        f"Unknown provider: {provider!r}. "
        "Supported: openai, google, gemini, ollama"
    )
