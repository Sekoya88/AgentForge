import asyncio
import json
import logging
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from app.domain.ports.redteam_engine import RedTeamEngine
from app.domain.value_objects import CampaignConfig
from app.infrastructure.redteam.config_generator import write_promptfoo_config

log = logging.getLogger(__name__)


class PromptfooRedTeamEngine(RedTeamEngine):
    """Runs `npx promptfoo eval` when Node + promptfoo are available; otherwise raises."""

    async def run_assessment(
        self,
        config: CampaignConfig,
        agent_label: str,
    ) -> dict[str, Any]:
        return await asyncio.to_thread(self._run_sync, config, agent_label)

    def _run_sync(self, config: CampaignConfig, agent_label: str) -> dict[str, Any]:
        if shutil.which("npx") is None:
            raise RuntimeError("npx not found; install Node.js or use REDTEAM_MODE=mock")

        with tempfile.TemporaryDirectory(prefix="af-promptfoo-") as tmp:
            tdir = Path(tmp)
            write_promptfoo_config(tdir, agent_label=agent_label, config=config.to_dict())
            out_json = tdir / "out.json"
            cmd = [
                "npx",
                "--yes",
                "promptfoo@latest",
                "eval",
                "-c",
                str(tdir / "promptfooconfig.yaml"),
                "--output",
                str(out_json),
            ]
            proc = subprocess.run(
                cmd,
                cwd=str(tdir),
                capture_output=True,
                text=True,
                timeout=300,
            )
            if proc.returncode != 0:
                log.warning("promptfoo_failed", extra={"stderr": proc.stderr[:2000]})
                raise RuntimeError(proc.stderr or proc.stdout or "promptfoo eval failed")

            if not out_json.is_file():
                raise RuntimeError("promptfoo did not write output file")

            raw = json.loads(out_json.read_text(encoding="utf-8"))
            return _normalize_promptfoo_output(raw, agent_label, config)


def _normalize_promptfoo_output(
    raw: dict[str, Any],
    agent_label: str,
    config: dict[str, Any],
) -> dict[str, Any]:
    results = raw.get("results") or raw.get("evals") or []
    if isinstance(results, dict):
        results = list(results.values())
    total = len(results) if results else 1
    passed = 0
    for r in results:
        if isinstance(r, dict):
            success = r.get("success", r.get("passed", True))
            if success:
                passed += 1
        else:
            passed += 1
    if total == 0:
        total = 1
    failed = total - passed
    score = round(100.0 * passed / total, 1)
    return {
        "overall_score": score,
        "total_tests": total,
        "passed_tests": passed,
        "failed_tests": failed,
        "report": {"engine": "promptfoo", "agent": agent_label, "config": config, "raw": raw},
        "vulnerabilities": {"uncategorized": {"severity": "info", "count": failed}},
    }
