from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status

from app.api.schemas.finetune_schemas import FinetuneCreateRequest, FinetuneJobResponse
from app.application.services.finetune_service import FinetuneService
from app.dependencies import get_current_user, get_finetune_service
from app.domain.entities.user import User

router = APIRouter(prefix="/finetune", tags=["finetune"])


@router.post("", response_model=FinetuneJobResponse, status_code=status.HTTP_201_CREATED)
async def create_finetune_job(
    body: FinetuneCreateRequest,
    user: Annotated[User, Depends(get_current_user)],
    svc: Annotated[FinetuneService, Depends(get_finetune_service)],
) -> FinetuneJobResponse:
    j = await svc.create(user.id, body.base_model, body.dataset_path, body.hyperparams)
    return FinetuneJobResponse.from_entity(j)


@router.get("", response_model=list[FinetuneJobResponse])
async def list_finetune_jobs(
    user: Annotated[User, Depends(get_current_user)],
    svc: Annotated[FinetuneService, Depends(get_finetune_service)],
) -> list[FinetuneJobResponse]:
    items = await svc.list_jobs(user.id)
    return [FinetuneJobResponse.from_entity(j) for j in items]


@router.get("/{job_id}", response_model=FinetuneJobResponse)
async def get_finetune_job(
    job_id: str,
    user: Annotated[User, Depends(get_current_user)],
    svc: Annotated[FinetuneService, Depends(get_finetune_service)],
) -> FinetuneJobResponse:
    j = await svc.get(UUID(job_id), user.id)
    return FinetuneJobResponse.from_entity(j)


@router.post("/{job_id}/deploy", response_model=FinetuneJobResponse)
async def deploy_finetune_stub(
    job_id: str,
    user: Annotated[User, Depends(get_current_user)],
    svc: Annotated[FinetuneService, Depends(get_finetune_service)],
) -> FinetuneJobResponse:
    j = await svc.deploy_stub(UUID(job_id), user.id)
    return FinetuneJobResponse.from_entity(j)


@router.delete("/{job_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_finetune_job(
    job_id: str,
    user: Annotated[User, Depends(get_current_user)],
    svc: Annotated[FinetuneService, Depends(get_finetune_service)],
) -> None:
    await svc.delete(UUID(job_id), user.id)
