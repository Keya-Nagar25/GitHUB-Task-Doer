import hashlib
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import yaml

from app.config import get_settings


@dataclass(frozen=True)
class IntentDef:
    intent_id: str
    action: str
    description: str
    param_schema: dict
    example_phrases: list[str]
    destructive: bool
    undo_strategy: str
    extra_warning: str | None = None


def _load_raw() -> list[dict]:
    path = Path(get_settings().intent_data_path).resolve()
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def intent_data_content_hash() -> str:
    path = Path(get_settings().intent_data_path).resolve()
    return hashlib.sha256(path.read_bytes()).hexdigest()


@lru_cache
def load_intents() -> list[IntentDef]:
    raw = _load_raw()
    return [
        IntentDef(
            intent_id=entry["intent_id"],
            action=entry["action"],
            description=entry["description"],
            param_schema=entry.get("param_schema") or {},
            example_phrases=entry["example_phrases"],
            destructive=entry.get("destructive", False),
            undo_strategy=entry.get("undo_strategy", "manual_only"),
            extra_warning=entry.get("extra_warning"),
        )
        for entry in raw
    ]


def get_intent(intent_id: str) -> IntentDef:
    for intent in load_intents():
        if intent.intent_id == intent_id:
            return intent
    raise KeyError(f"Unknown intent_id: {intent_id}")


# param_schema entries are either a type-hint placeholder ("str", "int", ...)
# meaning "extract this from the user's phrase", or a literal fixed value
# (e.g. mode: "soft") for intents that have no variable slots at all.
_TYPE_HINTS = {"str", "int", "bool", "list[str]"}


def default_params(intent: IntentDef) -> dict:
    """Fixed param values baked into this intent (not extracted from text)."""
    return {k: v for k, v in intent.param_schema.items() if v not in _TYPE_HINTS}
