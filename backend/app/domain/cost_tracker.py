from typing import TypedDict


class ModelPricing(TypedDict):
    prompt_tokens: float  # Cost per 1k tokens
    completion_tokens: float  # Cost per 1k tokens


# A very basic pricing table. In a real app, this should be fetched from DB or updated frequently.
PRICING_TABLE: dict[str, ModelPricing] = {
    "gpt-4o": {"prompt_tokens": 0.005, "completion_tokens": 0.015},
    "gpt-4o-mini": {"prompt_tokens": 0.00015, "completion_tokens": 0.0006},
    "claude-3-opus-20240229": {"prompt_tokens": 0.015, "completion_tokens": 0.075},
    "claude-3-5-sonnet-20240620": {"prompt_tokens": 0.003, "completion_tokens": 0.015},
    "claude-3-haiku-20240307": {"prompt_tokens": 0.00025, "completion_tokens": 0.00125},
    "gemini-1.5-pro": {"prompt_tokens": 0.0035, "completion_tokens": 0.0105},
    "gemini-1.5-flash": {"prompt_tokens": 0.00035, "completion_tokens": 0.00105},
    # Default fallback
    "default": {"prompt_tokens": 0.001, "completion_tokens": 0.002},
}


def calculate_cost(model_name: str | None, prompt_tokens: int, completion_tokens: int) -> float:
    """Calculate the estimated cost in USD based on token counts."""
    name = model_name or "default"
    # Find matching model or use default
    pricing = PRICING_TABLE.get(name)
    if not pricing:
        # Fallback to general patterns if precise match fails
        if "gpt-4o" in name:
            pricing = PRICING_TABLE["gpt-4o"]
        elif "claude-3-5-sonnet" in name:
            pricing = PRICING_TABLE["claude-3-5-sonnet-20240620"]
        elif "gemini-1.5-pro" in name:
            pricing = PRICING_TABLE["gemini-1.5-pro"]
        else:
            pricing = PRICING_TABLE["default"]

    cost = (prompt_tokens / 1000.0) * pricing["prompt_tokens"] + (
        completion_tokens / 1000.0
    ) * pricing["completion_tokens"]
    return cost
