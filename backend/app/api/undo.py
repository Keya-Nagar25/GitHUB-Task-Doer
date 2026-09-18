from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session

from app.actions.github_client import GithubApiError, GithubClient
from app.auth.crypto import decrypt_token
from app.auth.deps import get_current_session
from app.auth.models import UserSession
from app.db import get_db_session
from app.history.models import ActionLogEntry
from app.history.service import NotUndoableError, perform_undo

router = APIRouter()


class UndoResponse(BaseModel):
    status: str = "undone"
    result: dict


@router.post("/undo/{action_log_id}", response_model=UndoResponse)
def undo(
    action_log_id: str,
    session: UserSession = Depends(get_current_session),
    db: Session = Depends(get_db_session),
) -> UndoResponse:
    entry = db.get(ActionLogEntry, action_log_id)
    if entry is None or entry.github_user_id != session.github_user_id:
        raise HTTPException(status_code=404, detail="No such action")

    client = GithubClient(access_token=decrypt_token(session.encrypted_access_token))

    try:
        result = perform_undo(db, entry, client)
    except NotUndoableError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except GithubApiError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc

    return UndoResponse(result=result)
