from datetime import datetime, timezone

from sqlmodel import Field, SQLModel


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class UserSession(SQLModel, table=True):
    """An authenticated session, keyed by an opaque bearer token handed to the
    client after the GitHub OAuth callback. The GitHub access token is stored
    encrypted (see auth/crypto.py) -- never in plaintext at rest.
    """

    token: str = Field(primary_key=True)
    github_user_id: int = Field(index=True)
    github_login: str
    encrypted_access_token: bytes
    created_at: datetime = Field(default_factory=_utcnow)
