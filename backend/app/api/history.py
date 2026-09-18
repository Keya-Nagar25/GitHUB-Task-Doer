from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlmodel import Session, select

from app.actions.github_client import GithubClient
from app.auth.crypto import decrypt_token
from app.auth.deps import get_current_session
from app.auth.models import UserSession
from app.db import get_db_session
from app.history.models import ActionLogEntry

router = APIRouter()


class CommitSummary(BaseModel):
    sha: str
    message: str
    author: str | None
    date: str | None
    html_url: str


@router.get("/repo/{owner}/{repo}/history", response_model=list[CommitSummary])
def repo_history(
    owner: str,
    repo: str,
    limit: int = 20,
    session: UserSession = Depends(get_current_session),
) -> list[CommitSummary]:
    """Read-only commit history for time-travel browsing -- never mutates
    anything. Rolling back to an old version is a separate, explicitly
    destructive-flagged action (docs/architecture.md, Time-travel/rollback).
    """
    client = GithubClient(access_token=decrypt_token(session.encrypted_access_token))
    commits = client.list_commits(owner, repo, limit=limit)
    return [
        CommitSummary(
            sha=c["sha"],
            message=c["commit"]["message"],
            author=(c.get("author") or {}).get("login") or c["commit"]["author"]["name"],
            date=c["commit"]["author"]["date"],
            html_url=c["html_url"],
        )
        for c in commits
    ]


class ActionLogSummary(BaseModel):
    id: str
    action: str
    repo_owner: str
    repo_name: str
    undo_strategy: str
    undone: bool
    created_at: str


@router.get("/history/actions", response_model=list[ActionLogSummary])
def action_history(
    session: UserSession = Depends(get_current_session),
    db: Session = Depends(get_db_session),
) -> list[ActionLogSummary]:
    """This assistant's own action/undo log for the current user, separate
    from git's reflog or GitHub's commit history.
    """
    entries = db.exec(
        select(ActionLogEntry)
        .where(ActionLogEntry.github_user_id == session.github_user_id)
        .order_by(ActionLogEntry.created_at.desc())
    ).all()
    return [
        ActionLogSummary(
            id=e.id,
            action=e.action,
            repo_owner=e.repo_owner,
            repo_name=e.repo_name,
            undo_strategy=e.undo_strategy,
            undone=e.undone,
            created_at=e.created_at.isoformat(),
        )
        for e in entries
    ]
