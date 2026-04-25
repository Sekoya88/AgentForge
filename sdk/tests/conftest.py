import json
import os
import urllib.error
import urllib.request

import pytest

# Default Ollama host and preferred model (override with OLLAMA_MODEL if installed)
OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://localhost:11434").rstrip("/")
OLLAMA_MODEL_PREF = os.environ.get("OLLAMA_MODEL", "llama3.2").strip()


def is_ollama_running() -> bool:
    """Check if Ollama is running and accessible (stdlib only, no httpx)."""
    try:
        with urllib.request.urlopen(f"{OLLAMA_HOST}/api/tags", timeout=2.0) as resp:
            return resp.status == 200
    except (OSError, urllib.error.URLError, TimeoutError, ValueError):
        return False


def _ollama_installed_models() -> list[str]:
    """Return model names as reported by Ollama (e.g. 'llama3.2:latest')."""
    try:
        with urllib.request.urlopen(f"{OLLAMA_HOST}/api/tags", timeout=2.0) as resp:
            data = json.loads(resp.read().decode())
        models = data.get("models") or []
        return [str(m.get("name", "")).strip() for m in models if m.get("name")]
    except (OSError, urllib.error.URLError, TimeoutError, ValueError, json.JSONDecodeError):
        return []


def resolve_ollama_model_for_tests() -> str | None:
    """
    Pick a chat model for integration tests.
    Uses OLLAMA_MODEL if that exact name exists; otherwise first installed model.
    """
    if not is_ollama_running():
        return None
    installed = _ollama_installed_models()
    if not installed:
        return None
    pref = OLLAMA_MODEL_PREF
    if pref in installed:
        return pref
    # Allow short name match (user sets llama3.2, Ollama reports llama3.2:latest)
    for name in installed:
        if name == pref or name.startswith(pref + ":"):
            return name
    return installed[0]


@pytest.fixture(scope="session")
def ollama_model():
    """
    Model name for integration tests (must exist locally: `ollama pull ...`).
    """
    resolved = resolve_ollama_model_for_tests()
    if resolved is None:
        pytest.skip(
            f"No Ollama models at {OLLAMA_HOST}. Install Ollama and run "
            f"`ollama pull {OLLAMA_MODEL_PREF}` (or set OLLAMA_MODEL to an installed tag)."
        )
    return resolved


def pytest_runtest_setup(item):
    for _ in item.iter_markers(name="integration"):
        if resolve_ollama_model_for_tests() is None:
            pytest.skip(
                f"Ollama unavailable or has no models at {OLLAMA_HOST}. "
                f"Pull a model e.g. `ollama pull {OLLAMA_MODEL_PREF}`."
            )
