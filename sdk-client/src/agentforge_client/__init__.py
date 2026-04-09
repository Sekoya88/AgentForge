"""HTTP client for AgentForge API v1."""

from agentforge_client.budget import BudgetAPI
from agentforge_client.campaigns import CampaignsAPI
from agentforge_client.client import AgentforgeClient
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

__all__ = [
    "AgentforgeClient",
    "BudgetAPI",
    "CampaignsAPI",
    "ExecutionsAPI",
    "ExportAPI",
    "FinetuneAPI",
    "ForgeAPI",
    "GenerationAPI",
    "KnowledgeAPI",
    "MemoryAPI",
    "PiiAPI",
    "PromptOptimizerAPI",
    "SchedulesAPI",
    "SkillsAPI",
    "WebhooksAPI",
    "WorkspaceAPI",
]
