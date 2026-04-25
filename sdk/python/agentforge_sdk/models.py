"""Data models for AgentForge SDK responses."""
from __future__ import annotations
from dataclasses import dataclass, field


@dataclass
class ExecutionResult:
    id: str
    status: str          # "completed" | "failed" | "paused"
    output: str          # Last assistant message content
    token_usage: dict = field(default_factory=dict)
    duration_ms: int | None = None
    error: str | None = None


@dataclass
class Agent:
    id: str
    name: str
    description: str | None
    status: str          # "draft" | "live"


@dataclass
class Conversation:
    id: str
    agent_id: str
    thread_id: str
    title: str | None
    message_count: int
