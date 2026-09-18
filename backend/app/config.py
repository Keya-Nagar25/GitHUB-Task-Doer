import os
from functools import lru_cache

from pydantic import BaseModel


class Settings(BaseModel):
    anthropic_api_key: str | None = os.environ.get("ANTHROPIC_API_KEY")
    github_oauth_client_id: str | None = os.environ.get("GITHUB_OAUTH_CLIENT_ID")
    github_oauth_client_secret: str | None = os.environ.get("GITHUB_OAUTH_CLIENT_SECRET")
    github_oauth_redirect_uri: str = os.environ.get(
        "GITHUB_OAUTH_REDIRECT_URI", "http://localhost:8000/auth/github/callback"
    )
    github_api_base_url: str = os.environ.get("GITHUB_API_BASE_URL", "https://api.github.com")
    web_app_url: str = os.environ.get("WEB_APP_URL", "http://localhost:5173")
    # Origins the browser-facing web app is allowed to call this API from.
    # Defaults cover local dev on both loopback forms Vite may bind to;
    # web_app_url is included so a configured production frontend works too.
    cors_allowed_origins: list[str] = (
        os.environ["CORS_ALLOWED_ORIGINS"].split(",")
        if os.environ.get("CORS_ALLOWED_ORIGINS")
        else list({"http://localhost:5173", "http://127.0.0.1:5173", web_app_url})
    )
    # Fernet key (32 url-safe base64-encoded bytes) used to encrypt GitHub access
    # tokens at rest. Must be set in any persistent deployment -- an unset value
    # falls back to a per-process random key (see auth/crypto.py), which is fine
    # for local dev but invalidates all sessions on every restart.
    session_encryption_key: str | None = os.environ.get("SESSION_ENCRYPTION_KEY")
    database_url: str = os.environ.get("DATABASE_URL", "sqlite:///./taskdoer.db")
    intent_data_path: str = os.environ.get(
        "INTENT_DATA_PATH", os.path.join(os.path.dirname(__file__), "..", "..", "intent-data", "intents.yaml")
    )
    offline_high_confidence_threshold: float = 0.75
    offline_low_confidence_threshold: float = 0.55


@lru_cache
def get_settings() -> Settings:
    return Settings()
