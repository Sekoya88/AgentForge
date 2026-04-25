from fastapi import APIRouter

from app.api.v1 import (
    agents,
    auth,
    budget,
    campaigns,
    collab,
    dashboard,
    export,
    feedback,
    finetune,
    forge,
    generation,
    hub,
    knowledge,
    memory,
    pii,
    prompt_optimizer,
    proposals,
    sandbox,
    settings,
    skills,
    speech,
    sso,
    templates,
    user_preferences,
    webhooks,
    workspace,
)

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(auth.router)
api_router.include_router(agents.router)
api_router.include_router(export.router)
api_router.include_router(campaigns.router)
api_router.include_router(dashboard.router)
api_router.include_router(skills.router)
api_router.include_router(knowledge.router)
api_router.include_router(finetune.router)
api_router.include_router(speech.router)
api_router.include_router(sandbox.router)
api_router.include_router(generation.router)
api_router.include_router(templates.router)
api_router.include_router(settings.router)
api_router.include_router(user_preferences.router)
api_router.include_router(forge.router)
api_router.include_router(webhooks.router)
api_router.include_router(memory.router)
api_router.include_router(hub.router)
api_router.include_router(sso.router)
api_router.include_router(pii.router)
api_router.include_router(budget.router)
api_router.include_router(workspace.router)
api_router.include_router(prompt_optimizer.router)
api_router.include_router(collab.router)
api_router.include_router(feedback.router)
api_router.include_router(proposals.router)
