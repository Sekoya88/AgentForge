from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.application.services.generation_service import GenerationService
from app.dependencies import get_current_user
from app.domain.entities.user import User

router = APIRouter(prefix="/generate", tags=["generation"])


class GenerateRequest(BaseModel):
    prompt: str = Field(
        ...,
        json_schema_extra={"example": "Create a research agent that searches the web"},
    )


class GenerateAgentResponse(BaseModel):
    name: str
    description: str
    graph_definition: dict[str, Any]
    agent_model_config: dict[str, Any] = Field(..., alias="model_config")

    model_config = {"populate_by_name": True}


class GenerateSkillResponse(BaseModel):
    name: str
    description: str
    source_code: str
    parameters_schema: dict[str, Any]
    permissions: list[str]


@router.post("/agent", response_model=GenerateAgentResponse)
async def api_generate_agent(
    req: GenerateRequest,
    user: User = Depends(get_current_user),
) -> GenerateAgentResponse:
    svc = GenerationService()
    data = await svc.generate_agent(req.prompt)
    return GenerateAgentResponse(
        name=data.get("name", "Generated Agent"),
        description=data.get("description", ""),
        graph_definition=data.get("graph_definition", {}),
        model_config=data.get("model_config", {}),
    )


@router.post("/skill", response_model=GenerateSkillResponse)
async def api_generate_skill(
    req: GenerateRequest,
    user: User = Depends(get_current_user),
) -> GenerateSkillResponse:
    svc = GenerationService()
    data = await svc.generate_skill(req.prompt)
    return GenerateSkillResponse(
        name=data.get("name", "generated_skill"),
        description=data.get("description", ""),
        source_code=data.get("source_code", "def stub(): pass"),
        parameters_schema=data.get("parameters_schema", {}),
        permissions=data.get("permissions", []),
    )
