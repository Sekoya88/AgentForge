"""Sandboxed Python REPL for Forge Assistant — subprocess with timeout and output capture."""

from __future__ import annotations

import asyncio
import json as _json
import sys
import textwrap

# Hard limits
MAX_OUTPUT_CHARS = 4000
TIMEOUT_SECONDS = 10


async def python_repl(code: str, *, timeout: int = TIMEOUT_SECONDS) -> dict:
    """Execute Python code in a sandboxed subprocess with timeout.

    Returns dict with stdout, stderr, success flag, and truncation warning.
    Uses asyncio.create_subprocess_exec (no shell, no injection risk).
    """
    wrapped = textwrap.dedent(
        f"""
import sys, io, traceback
_stdout = io.StringIO()
_stderr = io.StringIO()
sys.stdout = _stdout
sys.stderr = _stderr
try:
    exec(compile({repr(code)}, "<forge>", "exec"), {{}})
    _exit_ok = True
except Exception:
    traceback.print_exc(file=_stderr)
    _exit_ok = False
finally:
    sys.stdout = sys.__stdout__
    sys.stderr = sys.__stderr__

out = _stdout.getvalue()
err = _stderr.getvalue()
import json, sys
sys.stdout.write(json.dumps({{"out": out, "err": err, "ok": _exit_ok}}))
"""
    ).strip()

    try:
        proc = await asyncio.create_subprocess_exec(
            sys.executable,
            "-c",
            wrapped,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout_bytes, stderr_bytes = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    except TimeoutError:
        return {
            "stdout": "",
            "stderr": f"Execution timed out after {timeout}s",
            "success": False,
            "truncated": False,
        }
    except Exception as e:
        return {"stdout": "", "stderr": str(e), "success": False, "truncated": False}

    raw = stdout_bytes.decode("utf-8", errors="replace").strip()
    try:
        result = _json.loads(raw)
        stdout = result.get("out", "")
        stderr = result.get("err", "")
        ok = bool(result.get("ok", False))
    except _json.JSONDecodeError:
        stdout = raw
        stderr = stderr_bytes.decode("utf-8", errors="replace")
        ok = proc.returncode == 0

    truncated = False
    if len(stdout) > MAX_OUTPUT_CHARS:
        stdout = stdout[:MAX_OUTPUT_CHARS] + "\n[... output truncated]"
        truncated = True
    if len(stderr) > MAX_OUTPUT_CHARS:
        stderr = stderr[:MAX_OUTPUT_CHARS] + "\n[... truncated]"

    return {"stdout": stdout, "stderr": stderr, "success": ok, "truncated": truncated}
