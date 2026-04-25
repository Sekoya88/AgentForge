from __future__ import annotations

import os
from typing import Any
from uuid import UUID

import httpx

from agentforge_client.budget import BudgetAPI
from agentforge_client.campaigns import CampaignsAPI
from agentforge_client.executions import ExecutionsAPI
from agentforge_client.export import ExportAPI
from agentforge_client.finetune import FinetuneAPI
from agentforge_client.forge import ForgeAPI
from agentforge_client.generation import GenerationAPI
from agentforge_client.knowledge import KnowledgeAPI
from agentforge_client.memory import MemoryAPI
from agentforge_client.pii import PiiAPI
from agentforge_client.prompt_optimizer import PromptOptimizerAPI
from agentforge_client.schedules import SchedulesAPI
from agentforge_client.skills import SkillsAPI
from agentforge_client.webhooks import WebhooksAPI
from agentforge_client.workspace import WorkspaceAPI


class AgentforgeClient:
    """Async client for the AgentForge API."""

    def __init__(
        self,
        *,
        base_url: str | None = None,
        access_token: str | None = None,
        timeout: float = 120.0,
    ) -> None:
        self._base = (base_url or os.environ.get("AGENTFORGE_API_URL") or "http://localhost:8000").rstrip(
            "/"
        )
        token = access_token or os.environ.get("AGENTFORGE_TOKEN")
        headers: dict[str, str] = {"Accept": "application/json"}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        self._client = httpx.AsyncClient(base_url=self._base, headers=headers, timeout=timeout)
        self._schedules = SchedulesAPI(self._client)
        self._skills = SkillsAPI(self._client)
        self._knowledge = KnowledgeAPI(self._client)
        self._campaigns = CampaignsAPI(self._client)
        self._finetune = FinetuneAPI(self._client)
        self._forge = ForgeAPI(self._client)
        self._executions = ExecutionsAPI(self._client)
        self._webhooks = WebhooksAPI(self._client)
        self._generation = GenerationAPI(self._client)
        self._memory = MemoryAPI(self._client)
        self._budget = BudgetAPI(self._client)
        self._pii = PiiAPI(self._client)
        self._prompt_optimizer = PromptOptimizerAPI(self._client)
        self._export = ExportAPI(self._client)
        self._workspace = WorkspaceAPI(self._client)

    @property
    def schedules(self) -> SchedulesAPI:
        """CRUD for cron schedules."""
        return self._schedules

    @property
    def skills(self) -> SkillsAPI:
        """CRUD for custom Python skills."""
        return self._skills

    @property
    def knowledge(self) -> KnowledgeAPI:
        """Ingest, search, and manage knowledge sources."""
        return self._knowledge

    @property
    def campaigns(self) -> CampaignsAPI:
        """Launch and inspect red-team campaigns."""
        return self._campaigns

    @property
    def finetune(self) -> FinetuneAPI:
        """Create and manage fine-tuning jobs."""
        return self._finetune

    @property
    def forge(self) -> ForgeAPI:
        """Direct LLM chat via Forge."""
        return self._forge

    @property
    def executions(self) -> ExecutionsAPI:
        """List, get, and interact with executions."""
        return self._executions

    @property
    def webhooks(self) -> WebhooksAPI:
        """CRUD for outbound webhooks."""
        return self._webhooks

    @property
    def generation(self) -> GenerationAPI:
        """AI-powered agent and skill generation."""
        return self._generation

    @property
    def memory(self) -> MemoryAPI:
        """Per-agent long-term memory entries."""
        return self._memory

    @property
    def budget(self) -> BudgetAPI:
        """Agent cost budget limits and spend tracking."""
        return self._budget

    @property
    def pii(self) -> PiiAPI:
        """PII detection and masking."""
        return self._pii

    @property
    def prompt_optimizer(self) -> PromptOptimizerAPI:
        """Automated A/B prompt optimization with LLM judging."""
        return self._prompt_optimizer

    @property
    def export(self) -> ExportAPI:
        """Export agents as Python scripts, Docker archives, or LangGraph JSON."""
        return self._export

    @property
    def workspace(self) -> WorkspaceAPI:
        """Workspace member management (invite, roles, remove)."""
        return self._workspace

    async def __aenter__(self) -> AgentforgeClient:
        return self

    async def __aexit__(self, *args: object) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        await self._client.aclose()

    async def list_agents(self) -> list[dict[str, Any]]:
        r = await self._client.get("/api/v1/agents")
        r.raise_for_status()
        return r.json()

    async def get_agent(self, agent_id: str | UUID) -> dict[str, Any]:
        r = await self._client.get(f"/api/v1/agents/{agent_id}")
        r.raise_for_status()
        return r.json()

    async def create_agent(
        self,
        *,
        name: str,
        graph_definition: dict[str, Any],
        model_config: dict[str, Any],
        description: str | None = None,
        skills: list[str] | None = None,
    ) -> dict[str, Any]:
        body: dict[str, Any] = {
            "name": name,
            "graph_definition": graph_definition,
            "model_config": model_config,
        }
        if description is not None:
            body["description"] = description
        if skills is not None:
            body["skills"] = skills
        r = await self._client.post("/api/v1/agents", json=body)
        r.raise_for_status()
        return r.json()

    async def execute_agent(
        self,
        agent_id: str | UUID,
        input_messages: list[dict[str, Any]],
        *,
        run_async: bool = False,
        version: int | None = None,
        alias: str | None = None,
    ) -> dict[str, Any]:
        body: dict[str, Any] = {
            "input_messages": input_messages,
            "run_async": run_async,
        }
        if version is not None:
            body["version"] = version
        if alias is not None:
            body["alias"] = alias
        r = await self._client.post(f"/api/v1/agents/{agent_id}/execute", json=body)
        r.raise_for_status()
        return r.json()

    async def get_execution(
        self, agent_id: str | UUID, execution_id: str | UUID
    ) -> dict[str, Any]:
        r = await self._client.get(f"/api/v1/agents/{agent_id}/executions/{execution_id}")
        r.raise_for_status()
        return r.json()

    async def list_speech_deployed(self) -> list[dict[str, Any]]:
        """Speech finetune jobs (``modality`` whisper / tts_voice) completed with ``inference_endpoint``."""
        r = await self._client.get("/api/v1/speech/deployed")
        r.raise_for_status()
        return r.json()
