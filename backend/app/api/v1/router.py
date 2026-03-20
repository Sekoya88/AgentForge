from fastapi import APIRouter

from app.api.v1 import agents, auth, campaigns, finetune, sandbox, skills

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(auth.router)
api_router.include_router(agents.router)
api_router.include_router(campaigns.router)
api_router.include_router(skills.router)
api_router.include_router(finetune.router)
api_router.include_router(sandbox.router)
