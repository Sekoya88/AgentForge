from __future__ import annotations

import logging
import re
from pathlib import Path

from app.infrastructure.persistence.postgres.forge_subagent_repo import ForgeSubAgentRepository
from app.infrastructure.persistence.postgres.session import session_scope

logger = logging.getLogger(__name__)

_DEFINITIONS_DIR = Path(__file__).parent / "definitions"

_DEFAULT_MODEL = {
    "provider": "anthropic",
    "model": "claude-haiku-4-5-20251001",
    "temperature": 0.2,
}

_TOOL_NAMES = [
    "create_proposal",
    "search_skills",
    "get_feedback_summary",
    "search_failed_executions",
]


def _parse_md(path: Path) -> dict:
    text = path.read_text()

    version_match = re.search(r"^version:\s*(\d+)", text, re.MULTILINE)
    version = int(version_match.group(1)) if version_match else 1

    h1_match = re.search(r"^#\s+(.+)", text, re.MULTILINE)
    display_name = h1_match.group(1).strip() if h1_match else path.stem

    model_config = dict(_DEFAULT_MODEL)
    provider_match = re.search(r"^provider:\s*(.+)", text, re.MULTILINE)
    model_match = re.search(r"^model:\s*(.+)", text, re.MULTILINE)
    temp_match = re.search(r"^temperature:\s*(.+)", text, re.MULTILINE)
    if provider_match:
        model_config["provider"] = provider_match.group(1).strip()
    if model_match:
        model_config["model"] = model_match.group(1).strip()
    if temp_match:
        try:
            model_config["temperature"] = float(temp_match.group(1).strip())
        except ValueError:
            logger.warning("Invalid temperature value in %s, using default", path)

    tools_section = re.search(r"## Tools\n(.*?)(?=##|\Z)", text, re.DOTALL)
    tools: list[str] = []
    if tools_section:
        for line in tools_section.group(1).splitlines():
            m = re.match(r"^\s*-\s*(\w+)", line)
            if m and m.group(1) in _TOOL_NAMES:
                tools.append(m.group(1))

    return {
        "display_name": display_name,
        "system_prompt": text,
        "tools": tools,
        "model_config": model_config,
        "version": version,
    }


async def setup_subagents() -> None:
    """Seed system sub-agent definitions from .md files into DB at startup."""
    md_files = list(_DEFINITIONS_DIR.glob("*.md"))
    if not md_files:
        return

    async with session_scope() as session:
        repo = ForgeSubAgentRepository(session)
        for md_path in md_files:
            name = md_path.stem  # filename without extension = agent name
            parsed = _parse_md(md_path)
            await repo.upsert_system(
                name=name,
                display_name=parsed["display_name"],
                system_prompt=parsed["system_prompt"],
                tools=parsed["tools"],
                model_config=parsed["model_config"],
                version=parsed["version"],
            )
