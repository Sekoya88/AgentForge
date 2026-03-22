"""Contract for default CI red-team engine (mock) — scores are synthetic, not real attacks."""

import pytest

from app.domain.value_objects import CampaignConfig
from app.infrastructure.redteam.mock_engine import _MOCK_TEST_TYPES, MockRedTeamEngine

pytestmark = pytest.mark.asyncio


async def test_mock_engine_exposes_stable_report_shape() -> None:
    eng = MockRedTeamEngine()
    out = await eng.run_assessment(CampaignConfig(), agent_label="ci-agent")
    assert out["report"]["engine"] == "mock"
    assert out["total_tests"] == len(_MOCK_TEST_TYPES)
    assert out["total_tests"] >= 10
    assert out["passed_tests"] + out["failed_tests"] == out["total_tests"]
    assert isinstance(out["overall_score"], float)
    assert "results" in out["report"]
