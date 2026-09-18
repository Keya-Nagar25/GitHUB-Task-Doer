import os
from functools import lru_cache

from pydantic import BaseModel


class Settings(BaseModel):
    anthropic_api_key: str | None = os.environ.get("ANTHROPIC_API_KEY")
    github_oauth_client_id: str | None = os.environ.get("GITHUB_OAUTH_CLIENT_ID")
    github_oauth_client_secret: str | None = os.environ.get("GITHUB_OAUTH_CLIENT_SECRET")
    database_url: str = os.environ.get("DATABASE_URL", "sqlite:///./taskdoer.db")
    intent_data_path: str = os.environ.get(
        "INTENT_DATA_PATH", os.path.join(os.path.dirname(__file__), "..", "..", "intent-data", "intents.yaml")
    )
    offline_high_confidence_threshold: float = 0.75
    offline_low_confidence_threshold: float = 0.55


@lru_cache
def get_settings() -> Settings:
    return Settings()
