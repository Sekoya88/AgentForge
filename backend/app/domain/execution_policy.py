"""Per-agent execution policy (tool allow/deny, fetch URL scope, graph step budget)."""

from __future__ import annotations

from typing import Any
from urllib.parse import urlparse

from pydantic import BaseModel, Field, field_validator


class ExecutionPolicyValidated(BaseModel):
    """JSON stored in agents.execution_policy / agent_versions.execution_policy."""

    allowed_tools: list[str] | None = Field(
        default=None,
        description="If set, only these tool names may run (built-ins + skill names).",
    )
    denied_tools: list[str] = Field(
        default_factory=list,
        description="Tool names always blocked.",
    )
    allowed_fetch_url_prefixes: list[str] | None = Field(
        default=None,
        description=(
            "If None, fetch URLs are unrestricted. If empty list, fetch is disabled. "
            "Otherwise URL string must start with one of these prefixes (after normalizing)."
        ),
    )
    max_graph_steps: int | None = Field(
        default=None,
        ge=1,
        le=500,
        description="LangGraph recursion_limit cap for this agent.",
    )
    deny_patterns: list[str] = Field(
        default_factory=list,
        description="Regex patterns applied to tool input text — blocks if any matches.",
    )
    require_human_approval_for: list[str] = Field(
        default_factory=list,
        description="Tool names that require a human-in-the-loop interrupt before execution.",
    )
    max_cost_usd: float | None = Field(
        default=None,
        ge=0.0,
        description="Max execution cost in USD. Halts execution if exceeded.",
    )
    max_message_history: int | None = Field(
        default=None,
        ge=2,
        description="Maximum number of messages to keep in context (sliding window).",
    )
    context_compression_threshold: int | None = Field(
        default=None,
        ge=1000,
        description="Number of tokens after which context compression is triggered.",
    )

    @field_validator("denied_tools", "allowed_tools")
    @classmethod
    def _strip_names(cls, v: list[str] | None) -> list[str] | None:
        if v is None:
            return None
        return [x.strip() for x in v if x and x.strip()]

    @field_validator("allowed_fetch_url_prefixes")
    @classmethod
    def _strip_prefixes(cls, v: list[str] | None) -> list[str] | None:
        if v is None:
            return None
        return [x.strip() for x in v if x and x.strip()]

    def to_dict(self) -> dict[str, Any]:
        return self.model_dump()

    def is_tool_allowed(self, tool_name: str) -> tuple[bool, str | None]:
        if tool_name in self.denied_tools:
            return False, f"tool {tool_name!r} is denied by execution policy"
        if self.allowed_tools is not None and tool_name not in self.allowed_tools:
            return False, f"tool {tool_name!r} is not in allowed_tools policy list"
        return True, None

    def is_input_allowed(self, tool_name: str, input_text: str) -> tuple[bool, str | None]:
        """Check if tool input matches any deny_patterns."""
        import re

        for pattern in self.deny_patterns:
            try:
                if re.search(pattern, input_text, re.IGNORECASE):
                    return False, f"Input blocked by deny_pattern: {pattern!r}"
            except re.error:
                pass  # Invalid regex — skip
        return True, None

    def is_fetch_url_allowed(self, url: str) -> tuple[bool, str | None]:
        if self.allowed_fetch_url_prefixes is None:
            return True, None
        if len(self.allowed_fetch_url_prefixes) == 0:
            return False, "fetch is disabled by execution policy (empty allowlist)"
        parsed = urlparse(url.strip())
        if parsed.scheme not in ("http", "https"):
            return False, "fetch URL must be http or https"
        normalized = url.strip()
        for prefix in self.allowed_fetch_url_prefixes:
            if normalized.startswith(prefix):
                return True, None
        return False, "fetch URL not allowed by execution policy prefix list"


def parse_execution_policy(raw: dict[str, Any] | None) -> ExecutionPolicyValidated:
    if not raw:
        return ExecutionPolicyValidated()
    return ExecutionPolicyValidated.model_validate(raw)
