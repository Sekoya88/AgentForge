"""Docker-isolated sandbox runtime.

Runs Python code inside a throwaway container with:
- --network none   (no network access)
- --memory 256m    (memory cap)
- --cpus 0.5       (CPU cap)
- --read-only      (immutable filesystem)
- Non-root user (nobody)

Falls back silently to a non-zero exit code on Docker errors so the
orchestrator can surface them as tool errors rather than crashing.
"""

import asyncio
import shlex

from app.domain.ports.sandbox_runtime import SandboxRuntime

_IMAGE = "python:3.12-slim"
_DOCKER_RUN = (
    "docker run --rm "
    "--network none "
    "--memory 256m "
    "--cpus 0.5 "
    "--read-only "
    "--tmpfs /tmp "
    "--user nobody "
    "{image} "
    "python -c {code}"
)


class DockerSandboxRuntime(SandboxRuntime):
    """Execute Python skills inside an ephemeral Docker container."""

    async def run_python(self, code: str, timeout_sec: float) -> tuple[int, str, str]:
        quoted_code = shlex.quote(code)
        cmd = _DOCKER_RUN.format(image=_IMAGE, code=quoted_code)

        try:
            proc = await asyncio.create_subprocess_shell(
                cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
        except FileNotFoundError:
            return 127, "", "Docker is not available on this host."

        try:
            out_b, err_b = await asyncio.wait_for(proc.communicate(), timeout=timeout_sec)
        except TimeoutError:
            proc.kill()
            await proc.wait()
            return 124, "", f"Execution timed out after {timeout_sec}s"

        out = out_b.decode(errors="replace") if out_b else ""
        err = err_b.decode(errors="replace") if err_b else ""
        rc = proc.returncode if proc.returncode is not None else -1
        return rc, out, err
