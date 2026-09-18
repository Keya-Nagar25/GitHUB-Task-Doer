import secrets
import time

import httpx
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from sqlmodel import Session

from app.auth.crypto import encrypt_token
from app.auth.models import UserSession
from app.config import get_settings
from app.db import get_db_session

router = APIRouter(prefix="/auth")

_GITHUB_AUTHORIZE_URL = "https://github.com/login/oauth/authorize"
_GITHUB_TOKEN_URL = "https://github.com/login/oauth/access_token"
_GITHUB_USER_URL = "https://api.github.com/user"
_OAUTH_SCOPES = "repo read:user"

# CSRF state store for the OAuth handshake. In-memory and single-process --
# fine for v1/dev; a multi-instance deployment needs this in Redis/the DB
# instead (flagged as a known v1 limitation, not a silent gap).
_STATE_TTL_SECONDS = 300
_pending_states: dict[str, float] = {}


def _issue_state() -> str:
    _prune_expired_states()
    state = secrets.token_urlsafe(24)
    _pending_states[state] = time.monotonic() + _STATE_TTL_SECONDS
    return state


def _consume_state(state: str) -> bool:
    _prune_expired_states()
    expiry = _pending_states.pop(state, None)
    return expiry is not None


def _prune_expired_states() -> None:
    now = time.monotonic()
    expired = [s for s, exp in _pending_states.items() if exp < now]
    for s in expired:
        _pending_states.pop(s, None)


class LoginResponse(BaseModel):
    authorize_url: str


@router.get("/github/login", response_model=LoginResponse)
def github_login() -> LoginResponse:
    settings = get_settings()
    if not settings.github_oauth_client_id:
        raise HTTPException(status_code=503, detail="GitHub OAuth is not configured on this server")

    state = _issue_state()
    query = httpx.QueryParams(
        {
            "client_id": settings.github_oauth_client_id,
            "redirect_uri": settings.github_oauth_redirect_uri,
            "scope": _OAUTH_SCOPES,
            "state": state,
        }
    )
    return LoginResponse(authorize_url=f"{_GITHUB_AUTHORIZE_URL}?{query}")


@router.get("/github/callback")
def github_callback(code: str, state: str, db: Session = Depends(get_db_session)) -> RedirectResponse:
    settings = get_settings()
    if not settings.github_oauth_client_id or not settings.github_oauth_client_secret:
        raise HTTPException(status_code=503, detail="GitHub OAuth is not configured on this server")

    if not _consume_state(state):
        raise HTTPException(status_code=400, detail="Invalid or expired OAuth state")

    with httpx.Client(timeout=10.0) as client:
        token_response = client.post(
            _GITHUB_TOKEN_URL,
            data={
                "client_id": settings.github_oauth_client_id,
                "client_secret": settings.github_oauth_client_secret,
                "code": code,
                "redirect_uri": settings.github_oauth_redirect_uri,
            },
            headers={"Accept": "application/json"},
        )
        token_response.raise_for_status()
        token_data = token_response.json()
        access_token = token_data.get("access_token")
        if not access_token:
            raise HTTPException(
                status_code=400,
                detail=f"GitHub did not return an access token: {token_data.get('error_description', token_data)}",
            )

        user_response = client.get(
            _GITHUB_USER_URL,
            headers={"Authorization": f"Bearer {access_token}", "Accept": "application/vnd.github+json"},
        )
        user_response.raise_for_status()
        user_data = user_response.json()

    session_token = secrets.token_urlsafe(32)
    session = UserSession(
        token=session_token,
        github_user_id=user_data["id"],
        github_login=user_data["login"],
        encrypted_access_token=encrypt_token(access_token),
    )
    db.add(session)
    db.commit()

    # Session token goes in the URL fragment, not the query string -- fragments
    # are never sent to servers, so this avoids the token landing in access
    # logs or a Referer header on the frontend's next request.
    query = httpx.QueryParams({"github_login": user_data["login"]})
    return RedirectResponse(
        f"{settings.web_app_url}/?{query}#session_token={session_token}"
    )
