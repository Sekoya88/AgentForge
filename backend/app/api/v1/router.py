from fastapi import APIRouter

from app.api.v1 import (
    agents,
    auth,
    campaigns,
    dashboard,
    finetune,
    forge,
    generation,
    knowledge,
    sandbox,
    settings,
    skills,
    speech,
    templates,
    webhooks,
)

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(auth.router)
api_router.include_router(agents.router)
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
api_router.include_router(forge.router)
api_router.include_router(webhooks.router)
