import uuid
from datetime import datetime, timezone

from sqlalchemy import JSON, Column
from sqlmodel import Field, SQLModel


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class ActionLogEntry(SQLModel, table=True):
    """A record of one executed action, separate from git's own reflog.

    pre_state/post_state let undo replay a computed action against what was
    actually recorded for *this* entry, rather than assuming "the last
    thing" -- see docs/architecture.md, Undo / history log.
    """

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    github_user_id: int = Field(index=True)
    action: str
    params: dict = Field(sa_column=Column(JSON))
    repo_owner: str
    repo_name: str
    pre_state: dict | None = Field(default=None, sa_column=Column(JSON))
    post_state: dict | None = Field(default=None, sa_column=Column(JSON))
    undo_strategy: str
    undone: bool = False
    created_at: datetime = Field(default_factory=_utcnow)
