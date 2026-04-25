from app.config import Settings
from app.dependencies import build_sandbox_runtime


def test_sandbox_factory_selects_docker() -> None:
    s = Settings(_env_file=None, SANDBOX_MODE="docker")  # type: ignore[call-arg]
    rt = build_sandbox_runtime(s)
    assert rt.__class__.__name__ == "DockerSandboxRuntime"


def test_sandbox_factory_default_subprocess() -> None:
    s = Settings(_env_file=None, SANDBOX_MODE="subprocess")  # type: ignore[call-arg]
    rt = build_sandbox_runtime(s)
    assert rt.__class__.__name__ == "SubprocessSandboxRuntime"
