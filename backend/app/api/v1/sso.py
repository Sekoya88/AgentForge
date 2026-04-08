"""
SSO / OIDC skeleton router.

This is a stub implementation — it provides the redirect plumbing for an
enterprise OIDC provider (Okta, Auth0, Azure AD, etc.) but does NOT fully
implement token exchange or session creation.  Those pieces are intentionally
left as 501 until the full OIDC integration is scoped.
"""

import secrets
import urllib.parse

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse, RedirectResponse

from app.config import get_settings

router = APIRouter(prefix="/sso", tags=["sso"])


def _sso_enabled() -> bool:
    s = get_settings()
    return bool(s.sso_oidc_issuer and s.sso_oidc_client_id and s.sso_oidc_client_secret)


@router.get("/config")
async def sso_config() -> dict:
    """
    Public endpoint — returns whether SSO is configured and the issuer URL.
    Frontend uses this to decide whether to show the SSO login button.
    """
    s = get_settings()
    return {
        "enabled": _sso_enabled(),
        "issuer": s.sso_oidc_issuer,
    }


@router.get("/login")
async def sso_login() -> RedirectResponse:
    """
    Redirects the browser to the OIDC provider's authorization endpoint.

    Constructs the authorization URL from the issuer's well-known discovery
    document convention: {issuer}/authorize  (works for Okta / Auth0 / Azure).
    If SSO is not configured, returns 501.

    NOTE: State parameter is generated but not yet persisted to a store —
    CSRF validation must be added before production use.
    """
    if not _sso_enabled():
        raise HTTPException(
            status_code=501,
            detail=(
                "SSO is not configured. Set SSO_OIDC_ISSUER, SSO_OIDC_CLIENT_ID, "
                "and SSO_OIDC_CLIENT_SECRET."
            ),
        )

    s = get_settings()

    # Derive authorization endpoint: {issuer}/authorize
    # Most OIDC providers (Okta, Auth0, Azure) follow this pattern.
    issuer = (s.sso_oidc_issuer or "").rstrip("/")
    auth_endpoint = f"{issuer}/authorize"

    state = secrets.token_urlsafe(32)

    params = {
        "response_type": "code",
        "client_id": s.sso_oidc_client_id,
        "redirect_uri": s.sso_oidc_redirect_uri or "",
        "scope": "openid email profile",
        "state": state,
    }

    redirect_url = f"{auth_endpoint}?{urllib.parse.urlencode(params)}"
    return RedirectResponse(url=redirect_url, status_code=302)


@router.get("/callback")
async def sso_callback(code: str | None = None, state: str | None = None) -> JSONResponse:
    """
    OIDC callback endpoint — receives authorization code from the provider.

    STUB: Validates that required params are present, then returns 501.
    Full implementation should:
      1. Validate `state` against the value stored at /login time (CSRF guard).
      2. POST to {issuer}/token to exchange `code` for id_token + access_token.
      3. Verify the id_token signature using provider's JWKS endpoint.
      4. Upsert the user in the DB, issue an AgentForge JWT, redirect to frontend.
    """
    if not code:
        raise HTTPException(
            status_code=400,
            detail="Missing required query parameter: code",
        )
    if not state:
        raise HTTPException(
            status_code=400,
            detail="Missing required query parameter: state",
        )

    return JSONResponse(
        status_code=501,
        content={
            "detail": "SSO callback not fully implemented",
            "stub": True,
            "received": {"code_present": True, "state_present": True},
            "next_steps": [
                "Validate state against session store (CSRF guard)",
                "POST to {issuer}/token to exchange code for tokens",
                "Verify id_token signature via JWKS",
                "Upsert user and issue AgentForge JWT",
                "Redirect browser to frontend /auth/callback with JWT",
            ],
        },
    )
