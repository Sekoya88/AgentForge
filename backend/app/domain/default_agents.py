"""Default agents seeded for every new user at registration time."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any
from uuid import UUID

from app.domain.skill_templates import SKILL_TEMPLATES

if TYPE_CHECKING:
    from app.application.services.agent_service import AgentService
    from app.application.services.skill_service import SkillService

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Definition of the 5 default agents
# ---------------------------------------------------------------------------

_DEFAULT_AGENTS: list[dict[str, Any]] = [
    {
        "name": "Assistant Personnel",
        "description": "Votre assistant quotidien: emails, résumés, questions générales",
        "graph_definition": {
            "nodes": [
                {
                    "id": "llm",
                    "type": "llm",
                    "config": {
                        "prompt": (
                            "Tu es un assistant personnel intelligent et efficace. "
                            "Tu aides avec l'organisation, la rédaction, les résumés et toutes les "
                            "questions du quotidien. Réponds toujours dans la langue "
                            "de l'utilisateur. Sois concis et actionnable."
                        )
                    },
                }
            ],
            "edges": [],
            "entry_point": "llm",
        },
        "model_config": {"provider": "google", "model": "gemini-3-flash"},
        "skills": ["summarize", "email_drafter", "meeting_notes"],
    },
    {
        "name": "Coach Code",
        "description": "Revue de code, debugging et suggestions d'amélioration",
        "graph_definition": {
            "nodes": [
                {
                    "id": "llm",
                    "type": "llm",
                    "config": {
                        "prompt": (
                            "Tu es un senior software engineer. "
                            "Tu revois le code, expliques les bugs et suggères des améliorations "
                            "concrètes. Tu montres toujours des exemples de code corrigé. "
                            "Tu es direct et précis."
                        )
                    },
                }
            ],
            "edges": [],
            "entry_point": "llm",
        },
        "model_config": {"provider": "anthropic", "model": "claude-sonnet-4-5"},
        "skills": ["code_review", "pr_description"],
    },
    {
        "name": "Analyste de Données",
        "description": "Extraction, analyse et visualisation de données structurées",
        "graph_definition": {
            "nodes": [
                {
                    "id": "llm",
                    "type": "llm",
                    "config": {
                        "prompt": (
                            "Tu es un data analyst expert. "
                            "Tu analyses des textes, CSV et JSON pour en extraire des insights. "
                            "Tu présentes toujours les résultats de façon structurée avec des "
                            "métriques clés et des conclusions actionnables."
                        )
                    },
                }
            ],
            "edges": [],
            "entry_point": "llm",
        },
        "model_config": {"provider": "openai", "model": "gpt-5.4-mini"},
        "skills": ["data_extract", "sentiment_analysis", "csv_analyzer", "json_transform"],
    },
    {
        "name": "Chercheur Web",
        "description": "Recherche et synthèse d'informations depuis le web et la littérature",
        "graph_definition": {
            "nodes": [
                {
                    "id": "llm",
                    "type": "llm",
                    "config": {
                        "prompt": (
                            "Tu es un chercheur rigoureux. "
                            "Tu explores les informations depuis le web et la littérature "
                            "scientifique. Tu cites toujours tes sources, distingues les faits "
                            "des opinions, et présentes des synthèses équilibrées."
                        )
                    },
                }
            ],
            "edges": [],
            "entry_point": "llm",
        },
        "model_config": {"provider": "google", "model": "gemini-3-flash"},
        "skills": ["web_search", "arxiv_search", "summarize"],
    },
    {
        "name": "Rédacteur",
        "description": "Rédaction, correction et reformulation de textes professionnels",
        "graph_definition": {
            "nodes": [
                {
                    "id": "llm",
                    "type": "llm",
                    "config": {
                        "prompt": (
                            "Tu es un expert en communication écrite. "
                            "Tu rédiges, corriges et reformules des textes professionnels: "
                            "emails, rapports, présentations. Tu t'adaptes au ton demandé et "
                            "au contexte de l'utilisateur."
                        )
                    },
                }
            ],
            "edges": [],
            "entry_point": "llm",
        },
        "model_config": {"provider": "openai", "model": "gpt-5.4-mini"},
        "skills": ["grammar_fixer", "tone_rewriter", "email_drafter", "translate"],
    },
]

# Pre-build a lookup of skill templates by name for fast access
_SKILL_TEMPLATE_BY_NAME: dict[str, dict[str, Any]] = {t["name"]: t for t in SKILL_TEMPLATES}


async def seed_default_agents(
    user_id: UUID,
    agent_service: AgentService,
    skill_service: SkillService,
) -> None:
    """Create 5 default agents (with their required skills) for a new user.

    Errors are caught per-agent so a single failure does not prevent the rest
    from being created.
    """
    for defn in _DEFAULT_AGENTS:
        try:
            skill_ids = await _ensure_skills(user_id, defn["skills"], skill_service)
            await agent_service.create(
                user_id=user_id,
                name=defn["name"],
                description=defn["description"],
                graph_definition=defn["graph_definition"],
                model_config=defn["model_config"],
                skills=skill_ids if skill_ids else None,
            )
            log.info("Seeded default agent %r for user %s", defn["name"], user_id)
        except Exception:
            log.exception("Failed to seed default agent %r for user %s", defn["name"], user_id)


async def _ensure_skills(
    user_id: UUID,
    skill_names: list[str],
    skill_service: SkillService,
) -> list[str]:
    """Create skills from templates (if they don't already exist) and return their UUIDs."""
    ids: list[str] = []
    for name in skill_names:
        tpl = _SKILL_TEMPLATE_BY_NAME.get(name)
        if tpl is None:
            log.warning("Skill template %r not found — skipping", name)
            continue
        try:
            skill = await skill_service.create(
                user_id=user_id,
                name=tpl["name"],
                description=tpl.get("description"),
                skill_type=tpl["skill_type"],
                source_code=tpl.get("source_code", ""),
                instructions=tpl.get("instructions"),
                parameters_schema=tpl.get("parameters_schema", {}),
                permissions=tpl.get("permissions", []),
                is_public=tpl.get("is_public", False),
            )
            ids.append(str(skill.id))
        except Exception:
            log.exception("Failed to create skill %r for user %s", name, user_id)
    return ids
