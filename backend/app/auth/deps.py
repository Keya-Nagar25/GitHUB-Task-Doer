from cryptography.fernet import InvalidToken
from fastapi import Depends, Header, HTTPException
from sqlmodel import Session

from app.auth.crypto import decrypt_token
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

    # The stored GitHub token is unreadable if it was encrypted with a key
    # from an earlier server run (no persistent SESSION_ENCRYPTION_KEY set --
    # see auth/crypto.py). Without this check every endpoint would crash with
    # a 500 on decrypt; instead the session is dropped and the client is told
    # to log in again.
    try:
        decrypt_token(session.encrypted_access_token)
    except InvalidToken:
        db.delete(session)
        db.commit()
        raise HTTPException(
            status_code=401, detail="Your login expired (the server restarted). Please log in with GitHub again."
        ) from None
    return session
