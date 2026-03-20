import asyncio
import sys

from app.domain.ports.sandbox_runtime import SandboxRuntime


class SubprocessSandboxRuntime(SandboxRuntime):
    async def run_python(self, code: str, timeout_sec: float) -> tuple[int, str, str]:
        proc = await asyncio.create_subprocess_exec(
            sys.executable,
            "-c",
            code,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            out_b, err_b = await asyncio.wait_for(proc.communicate(), timeout=timeout_sec)
        except TimeoutError:
            proc.kill()
            await proc.wait()
            return 124, "", "Execution timed out"
        out = out_b.decode(errors="replace") if out_b else ""
        err = err_b.decode(errors="replace") if err_b else ""
        code_exit = proc.returncode if proc.returncode is not None else -1
        return code_exit, out, err
