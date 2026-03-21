import asyncio
from typing import Any

from app.domain.ports.redteam_engine import RedTeamEngine
from app.domain.value_objects import CampaignConfig

# ≥10 distinct test categories (US-002 / roadmap)
_MOCK_TEST_TYPES: list[tuple[str, str]] = [
    ("prompt-injection", "high"),
    ("jailbreak-basic", "high"),
    ("tool-misuse", "medium"),
    ("data-exfiltration", "high"),
    ("pii-leakage", "critical"),
    ("role-confusion", "medium"),
    ("encoding-tricks", "low"),
    ("indirect-injection", "high"),
    ("system-prompt-leak", "medium"),
    ("denial-of-service-prompt", "low"),
    ("policy-evasion", "medium"),
    ("multilingual-jailbreak", "medium"),
]


class MockRedTeamEngine(RedTeamEngine):
    async def run_assessment(
        self,
        config: CampaignConfig,
        agent_label: str,
    ) -> dict[str, Any]:
        await asyncio.sleep(0)
        results: list[dict[str, Any]] = []
        vulnerabilities: dict[str, Any] = {}
        for i, (name, severity) in enumerate(_MOCK_TEST_TYPES):
            passed = (i % 4) != 1
            results.append(
                {
                    "test_type": name,
                    "passed": passed,
                    "severity": severity,
                    "detail": "Synthetic check (mock engine)",
                }
            )
            if not passed:
                vulnerabilities[name] = {"severity": severity, "count": 1}
            else:
                vulnerabilities[name] = {"severity": severity, "count": 0}

        total = len(results)
        passed_n = sum(1 for r in results if r["passed"])
        failed_n = total - passed_n
        score = round(100.0 * passed_n / total, 1) if total else 0.0

        return {
            "overall_score": score,
            "total_tests": total,
            "passed_tests": passed_n,
            "failed_tests": failed_n,
            "report": {
                "engine": "mock",
                "agent": agent_label,
                "config": config.to_dict(),
                "results": results,
                "summary": f"{passed_n}/{total} checks passed",
            },
            "vulnerabilities": vulnerabilities,
        }
