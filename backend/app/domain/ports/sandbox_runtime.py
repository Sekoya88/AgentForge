from abc import ABC, abstractmethod


class SandboxRuntime(ABC):
    @abstractmethod
    async def run_python(self, code: str, timeout_sec: float) -> tuple[int, str, str]:
        """Run Python code in an isolated subprocess. Returns (exit_code, stdout, stderr)."""
