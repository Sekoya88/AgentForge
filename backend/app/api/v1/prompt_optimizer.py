"""Automatic prompt optimizer — generate A/B system prompt variants and score them.

Flow:
  1. POST /optimize  — given an agent_id + test_input, generate N prompt variants
                       using the LLM, then score each with an LLM judge.
  2. GET  /optimize/{job_id} — poll the result.

Results are stored in Redis (TTL 24h) so no DB migration is needed.
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from typing import Annotated, Any
from uuid import UUID

import redis.asyncio as redis
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.dependencies import (
    get_agent_repository,
    get_current_user,
    get_redis_optional,
    get_settings_dep,
)
from app.domain.entities.user import User
from app.domain.ports.agent_repository import AgentRepository

router = APIRouter(prefix="/prompt-optimizer", tags=["prompt-optimizer"])

_TTL_SECONDS = 86_400  # 24 h


# ── Schemas ────────────────────────────────────────────────────────────────────


class OptimizeRequest(BaseModel):
    agent_id: UUID
    test_input: str = Field(min_length=1, max_length=2000)
    num_variants: int = Field(default=3, ge=2, le=5)
    judge_criteria: str = Field(
        default="helpfulness, conciseness, factual accuracy",
        max_length=200,
    )


class VariantResult(BaseModel):
    variant_id: str
    system_prompt: str
    response: str
    score: float  # 0-10 from LLM judge
    judge_rationale: str


class OptimizeResponse(BaseModel):
    job_id: str
    agent_id: UUID
    status: str  # "pending" | "completed" | "error"
    created_at: str
    variants: list[VariantResult] = []
    winner_variant_id: str | None = None
    error: str | None = None


# ── Helpers ────────────────────────────────────────────────────────────────────


def _extract_system_prompt(graph_def: dict[str, Any]) -> str:
    for node in graph_def.get("nodes", []):
        sp = (node.get("config") or {}).get("system_prompt", "")
        if sp:
            return str(sp)
    return "You are a helpful assistant."


async def _call_llm(prompt: str, *, settings: Any, system: str | None = None) -> str:
    """Call the first available LLM (OpenAI → Anthropic → error)."""
    if settings.openai_api_key:
        from openai import AsyncOpenAI

        client = AsyncOpenAI(api_key=settings.openai_api_key)
        msgs = []
        if system:
            msgs.append({"role": "system", "content": system})
        msgs.append({"role": "user", "content": prompt})
        resp = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=msgs,
            max_tokens=800,
            temperature=0.7,
        )
        return resp.choices[0].message.content or ""

    if settings.anthropic_api_key:
        import anthropic

        client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
        kwargs: dict[str, Any] = {
            "model": "claude-haiku-4-5-20251001",
            "max_tokens": 800,
            "messages": [{"role": "user", "content": prompt}],
        }
        if system:
            kwargs["system"] = system
        resp = await client.messages.create(**kwargs)
        return resp.content[0].text if resp.content else ""

    raise RuntimeError("No LLM API key configured (OPENAI_API_KEY or ANTHROPIC_API_KEY required)")


async def _run_optimization(
    job_id: str,
    agent_id: UUID,
    original_prompt: str,
    test_input: str,
    num_variants: int,
    judge_criteria: str,
    settings: Any,
    r: redis.Redis,
) -> None:
    """Background coroutine — generates variants and scores them, stores result in Redis."""
    key = f"prompt_opt:{job_id}"
    variants: list[VariantResult] = []

    try:
        # Step 1: Generate N prompt variants
        gen_prompt = (
            f"You are an expert prompt engineer. Given the system prompt below, generate "
            f"{num_variants} improved variants. Each variant should try a different angle "
            f"(e.g. more concise, more detailed, role-play style, chain-of-thought, etc.).\n\n"
            f"Original prompt:\n{original_prompt}\n\n"
            f"Return ONLY a JSON array of {num_variants} strings, one per variant. "
            f"No explanation, no markdown, just the JSON array."
        )
        raw_variants = await _call_llm(gen_prompt, settings=settings)
        try:
            prompt_list: list[str] = json.loads(raw_variants)
            if not isinstance(prompt_list, list):
                prompt_list = [original_prompt] * num_variants
        except json.JSONDecodeError:
            prompt_list = [original_prompt] * num_variants
        prompt_list = prompt_list[:num_variants]

        # Step 2: Get response for each variant
        for i, sys_prompt in enumerate(prompt_list):
            try:
                response = await _call_llm(test_input, settings=settings, system=sys_prompt)
            except Exception:
                response = "[LLM error]"

            # Step 3: Judge score
            judge_prompt = (
                f"You are an impartial judge evaluating LLM responses.\n"
                f"Criteria: {judge_criteria}\n\n"
                f"System prompt used:\n{sys_prompt}\n\n"
                f"User input: {test_input}\n\n"
                f"Response: {response}\n\n"
                f"Score the response from 0 to 10. "
                f'Return JSON: {{"score": <float>, "rationale": "<one sentence>"}}'
            )
            try:
                judge_raw = await _call_llm(judge_prompt, settings=settings)
                judge_data = json.loads(judge_raw)
                score = float(judge_data.get("score", 5.0))
                rationale = str(judge_data.get("rationale", ""))
            except Exception:
                score = 5.0
                rationale = "Judge evaluation failed"

            variants.append(
                VariantResult(
                    variant_id=f"v{i + 1}",
                    system_prompt=sys_prompt,
                    response=response,
                    score=round(score, 2),
                    judge_rationale=rationale,
                )
            )

        winner = max(variants, key=lambda v: v.score).variant_id if variants else None

        result = OptimizeResponse(
            job_id=job_id,
            agent_id=agent_id,
            status="completed",
            created_at=datetime.now(UTC).isoformat(),
            variants=variants,
            winner_variant_id=winner,
        )
    except Exception as exc:
        result = OptimizeResponse(
            job_id=job_id,
            agent_id=agent_id,
            status="error",
            created_at=datetime.now(UTC).isoformat(),
            error=str(exc),
        )

    await r.set(key, result.model_dump_json(), ex=_TTL_SECONDS)


# ── Endpoints ──────────────────────────────────────────────────────────────────


@router.post("", response_model=OptimizeResponse, status_code=status.HTTP_202_ACCEPTED)
async def start_optimization(
    body: OptimizeRequest,
    user: Annotated[User, Depends(get_current_user)],
    repo: Annotated[AgentRepository, Depends(get_agent_repository)],
    settings: Annotated[Any, Depends(get_settings_dep)],
    r: Annotated[redis.Redis | None, Depends(get_redis_optional)],
) -> OptimizeResponse:
    """Start a prompt optimization job. Returns immediately with a job_id to poll."""
    if r is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Prompt optimizer requires Redis",
        )
    agent = await repo.get_by_id(body.agent_id, user.id)
    if agent is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")

    original_prompt = _extract_system_prompt(
        agent.graph_definition
        if isinstance(agent.graph_definition, dict)
        else agent.graph_definition.model_dump()
    )

    job_id = uuid.uuid4().hex
    pending = OptimizeResponse(
        job_id=job_id,
        agent_id=body.agent_id,
        status="pending",
        created_at=datetime.now(UTC).isoformat(),
    )
    await r.set(f"prompt_opt:{job_id}", pending.model_dump_json(), ex=_TTL_SECONDS)

    # Run in background (fire-and-forget via asyncio.create_task)
    import asyncio

    asyncio.create_task(
        _run_optimization(
            job_id=job_id,
            agent_id=body.agent_id,
            original_prompt=original_prompt,
            test_input=body.test_input,
            num_variants=body.num_variants,
            judge_criteria=body.judge_criteria,
            settings=settings,
            r=r,
        )
    )
    return pending


@router.get("/{job_id}", response_model=OptimizeResponse)
async def get_optimization_result(
    job_id: str,
    user: Annotated[User, Depends(get_current_user)],
    r: Annotated[redis.Redis | None, Depends(get_redis_optional)],
) -> OptimizeResponse:
    """Poll for the result of a prompt optimization job."""
    if r is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Redis unavailable"
        )
    raw = await r.get(f"prompt_opt:{job_id}")
    if raw is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Job not found or expired"
        )
    return OptimizeResponse.model_validate_json(raw)
