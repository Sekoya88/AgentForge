from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from app.domain.entities.agent import Agent


class BudgetService:
    """Estimates LLM token costs and checks agent budget limits."""

    COST_PER_1K_TOKENS: float = 0.002  # USD

    def estimate_cost_usd(self, token_usage: dict[str, Any] | None) -> float:
        """Sum prompt + completion tokens across a token_usage dict and apply cost rate.

        Supports both flat dicts ({"prompt_tokens": N, "completion_tokens": N})
        and nested dicts where values are themselves dicts with those keys.
        """
        if not token_usage:
            return 0.0

        total_tokens = 0

        # Flat structure: {"prompt_tokens": N, "completion_tokens": N, ...}
        if "prompt_tokens" in token_usage or "completion_tokens" in token_usage:
            total_tokens += int(token_usage.get("prompt_tokens", 0) or 0)
            total_tokens += int(token_usage.get("completion_tokens", 0) or 0)
        else:
            # Nested structure: {"node_name": {"prompt_tokens": N, ...}, ...}
            for value in token_usage.values():
                if isinstance(value, dict):
                    total_tokens += int(value.get("prompt_tokens", 0) or 0)
                    total_tokens += int(value.get("completion_tokens", 0) or 0)
                elif isinstance(value, int | float):
                    total_tokens += int(value)

        return round(total_tokens * self.COST_PER_1K_TOKENS / 1000, 6)

    def check_budget(self, agent: Agent, spent_usd: float) -> dict:
        """Return budget status for an agent given current spend.

        Returns a dict with keys:
          - status: "ok" | "warning" | "exceeded"
          - spent: float
          - limit: float | None
          - alert_threshold: float
        """
        limit = agent.budget_limit_usd
        threshold = agent.budget_alert_threshold

        if limit is None:
            return {
                "status": "ok",
                "spent": spent_usd,
                "limit": None,
                "alert_threshold": threshold,
            }

        if spent_usd >= limit:
            status = "exceeded"
        elif limit > 0 and spent_usd / limit >= threshold:
            status = "warning"
        else:
            status = "ok"

        return {
            "status": status,
            "spent": spent_usd,
            "limit": limit,
            "alert_threshold": threshold,
        }
