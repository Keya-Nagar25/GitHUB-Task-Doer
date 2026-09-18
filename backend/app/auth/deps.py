from fastapi import Depends, Header, HTTPException
from sqlmodel import Session

from app.auth.models import UserSession
from app.db import get_db_session


def get_current_session(
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db_session),
) -> UserSession:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or malformed Authorization header")

    token = authorization.removeprefix("Bearer ").strip()
    session = db.get(UserSession, token)
    if session is None:
        raise HTTPException(status_code=401, detail="Invalid or expired session")
    return session
