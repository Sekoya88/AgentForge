from typing import Any

from app.domain.cost_tracker import calculate_cost


class ExecutionCostMeter:
    """Tracks token usage and calculates costs during graph execution."""

    def __init__(self, max_cost_usd: float | None = None):
        self.total_prompt_tokens = 0
        self.total_completion_tokens = 0
        self.total_cost_usd = 0.0
        self.max_cost_usd = max_cost_usd

    def add_usage(self, model_name: str, usage: dict[str, Any]) -> None:
        """Add token usage from a single LLM invocation and update cost."""
        prompt = usage.get("prompt_tokens", 0)
        completion = usage.get("completion_tokens", 0)

        self.total_prompt_tokens += prompt
        self.total_completion_tokens += completion

        cost = calculate_cost(model_name, prompt, completion)
        self.total_cost_usd += cost

    def check_budget(self) -> None:
        """Raise an exception if the cost exceeds the allowed budget."""
        if self.max_cost_usd is not None and self.total_cost_usd > self.max_cost_usd:
            raise RuntimeError(
                f"Execution exceeded budget: ${self.total_cost_usd:.4f} > ${self.max_cost_usd:.4f}"
            )

    def get_token_usage_dict(self) -> dict[str, Any]:
        """Return a dictionary of usage metrics to attach to the Execution."""
        return {
            "prompt_tokens": self.total_prompt_tokens,
            "completion_tokens": self.total_completion_tokens,
            "total_tokens": self.total_prompt_tokens + self.total_completion_tokens,
            "estimated_cost_usd": self.total_cost_usd,
        }
