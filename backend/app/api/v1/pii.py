"""PII masking preview endpoint."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.dependencies import get_current_user
from app.domain.entities.user import User
from app.domain.services.pii_masker import PiiMasker

router = APIRouter(prefix="/pii", tags=["pii"])

_masker = PiiMasker()


class PiiMaskRequest(BaseModel):
    text: str


class PiiMaskResponse(BaseModel):
    masked: str
    hits: int


@router.post("/mask", response_model=PiiMaskResponse)
async def mask_pii(
    body: PiiMaskRequest,
    _user: Annotated[User, Depends(get_current_user)],
) -> PiiMaskResponse:
    """Mask PII in the provided text.

    Useful for previewing what the masker will redact before storing or
    returning execution traces.  Requires authentication.
    """
    masked, hits = _masker.mask(body.text)
    return PiiMaskResponse(masked=masked, hits=hits)
