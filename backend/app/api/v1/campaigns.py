from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status

from app.api.schemas.campaign_schemas import CampaignResponse, LaunchCampaignRequest
from app.application.services.campaign_service import CampaignService
from app.dependencies import get_campaign_service, get_current_user
from app.domain.entities.user import User

router = APIRouter(prefix="/campaigns", tags=["campaigns"])


@router.post("", response_model=CampaignResponse, status_code=status.HTTP_201_CREATED)
async def launch_campaign(
    body: LaunchCampaignRequest,
    user: Annotated[User, Depends(get_current_user)],
    svc: Annotated[CampaignService, Depends(get_campaign_service)],
) -> CampaignResponse:
    c = await svc.launch(
        user.id,
        body.agent_id,
        body.plugins,
        body.strategies,
        run_async=body.run_async,
    )
    return CampaignResponse.from_entity(c)


@router.get("", response_model=list[CampaignResponse])
async def list_campaigns(
    user: Annotated[User, Depends(get_current_user)],
    svc: Annotated[CampaignService, Depends(get_campaign_service)],
) -> list[CampaignResponse]:
    items = await svc.list_campaigns(user.id)
    return [CampaignResponse.from_entity(c) for c in items]


@router.get("/{campaign_id}", response_model=CampaignResponse)
async def get_campaign(
    campaign_id: str,
    user: Annotated[User, Depends(get_current_user)],
    svc: Annotated[CampaignService, Depends(get_campaign_service)],
) -> CampaignResponse:
    c = await svc.get(UUID(campaign_id), user.id)
    return CampaignResponse.from_entity(c)


@router.get("/{campaign_id}/report")
async def get_campaign_report(
    campaign_id: str,
    user: Annotated[User, Depends(get_current_user)],
    svc: Annotated[CampaignService, Depends(get_campaign_service)],
) -> dict:
    return await svc.report_payload(UUID(campaign_id), user.id)


@router.delete("/{campaign_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_campaign(
    campaign_id: str,
    user: Annotated[User, Depends(get_current_user)],
    svc: Annotated[CampaignService, Depends(get_campaign_service)],
) -> None:
    await svc.delete(UUID(campaign_id), user.id)
