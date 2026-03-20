from app.config import Settings
from app.domain.ports.redteam_engine import RedTeamEngine
from app.infrastructure.redteam.mock_engine import MockRedTeamEngine
from app.infrastructure.redteam.promptfoo_engine import PromptfooRedTeamEngine


def redteam_engine_from_settings(settings: Settings) -> RedTeamEngine:
    mode = (settings.redteam_mode or "mock").strip().lower()
    if mode == "promptfoo":
        return PromptfooRedTeamEngine()
    return MockRedTeamEngine()
