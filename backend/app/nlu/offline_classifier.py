import json
import re
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from app.config import get_settings
from app.nlu.intent_catalog import IntentDef, default_params, intent_data_content_hash, load_intents

_CACHE_DIR = Path(__file__).resolve().parent.parent.parent.parent / "intent-data" / "embeddings_cache"
_MODEL_NAME = "all-MiniLM-L6-v2"
# Bump when the embedding text derivation changes, so stale caches on disk
# (keyed only by intents.yaml content) get rebuilt.
_CACHE_FORMAT_VERSION = 2

_model = None  # lazy singleton, avoids reloading the model on every call


def _get_model():
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer

        _model = SentenceTransformer(_MODEL_NAME)
    return _model


@dataclass(frozen=True)
class _PhraseEntry:
    intent_id: str
    template: str


def _embedding_text(template: str) -> str:
    # Strip "{param}" placeholders before embedding: MiniLM cosine similarity
    # between a short template and a longer real sentence with slot content
    # (e.g. a title/message) is noisy when the raw braces are embedded too.
    # This fallback path only needs to capture the surrounding intent, since
    # exact/near-exact phrasing is already handled by _structural_match.
    return re.sub(r"\{[a-zA-Z_]+\}", "", template).strip()


def _all_phrase_entries() -> list[_PhraseEntry]:
    entries: list[_PhraseEntry] = []
    for intent in load_intents():
        for phrase in intent.example_phrases:
            entries.append(_PhraseEntry(intent_id=intent.intent_id, template=phrase))
    return entries


def _load_or_build_embeddings() -> tuple[list[_PhraseEntry], np.ndarray]:
    entries = _all_phrase_entries()
    content_hash = intent_data_content_hash()

    _CACHE_DIR.mkdir(parents=True, exist_ok=True)
    meta_path = _CACHE_DIR / "meta.json"
    vectors_path = _CACHE_DIR / "vectors.npy"

    if meta_path.exists() and vectors_path.exists():
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        if (
            meta.get("content_hash") == content_hash
            and meta.get("model") == _MODEL_NAME
            and meta.get("format_version") == _CACHE_FORMAT_VERSION
        ):
            vectors = np.load(vectors_path)
            if vectors.shape[0] == len(entries):
                return entries, vectors

    model = _get_model()
    texts = [_embedding_text(e.template) for e in entries]
    vectors = model.encode(texts, normalize_embeddings=True)
    np.save(vectors_path, vectors)
    meta_path.write_text(
        json.dumps(
            {"content_hash": content_hash, "model": _MODEL_NAME, "format_version": _CACHE_FORMAT_VERSION}
        ),
        encoding="utf-8",
    )
    return entries, vectors


def _template_to_regex(template: str) -> re.Pattern:
    # Turn "commit everything with the message {message}" into a regex that
    # captures {message} while matching the surrounding literal text exactly.
    parts = re.split(r"(\{[a-zA-Z_]+\})", template)
    pattern_parts = []
    for part in parts:
        m = re.fullmatch(r"\{([a-zA-Z_]+)\}", part)
        if m:
            pattern_parts.append(f"(?P<{m.group(1)}>.+)")
        else:
            pattern_parts.append(re.escape(part))
    return re.compile("^" + "".join(pattern_parts) + "$", re.IGNORECASE)


def _extract_params(text: str, intent: IntentDef) -> dict:
    for template in intent.example_phrases:
        if "{" not in template:
            continue
        match = _template_to_regex(template).match(text.strip())
        if match:
            return {k: v.strip() for k, v in match.groupdict().items()}
    return {}


def _structural_match(text: str) -> tuple[IntentDef, dict] | None:
    """Exact/template-shaped match against every known phrase, across all
    intents. This is the primary matcher: an input that exactly matches a
    known phrasing (e.g. "commit everything with the message {message}")
    should never be at the mercy of embedding-similarity noise.
    """
    normalized = text.strip()
    for intent in load_intents():
        for template in intent.example_phrases:
            match = _template_to_regex(template).match(normalized)
            if match:
                return intent, {k: v.strip() for k, v in match.groupdict().items()}
    return None


@dataclass(frozen=True)
class OfflineResolution:
    matched: bool
    intent: IntentDef | None
    params: dict
    similarity: float
    confidence: str  # "high" | "medium" | "none"
    message: str | None = None  # set when matched is False, or as a "did you mean" hint


def resolve_offline(text: str) -> OfflineResolution:
    """Pure, offline, deterministic intent resolution. No network calls.

    Tries an exact/template-shaped structural match first (fast, unambiguous).
    Falls back to embedding similarity for paraphrases the templates don't
    literally cover. Never fabricates a match below the low-confidence
    threshold -- returns matched=False with a message asking the user to
    rephrase or go online instead of guessing.
    """
    structural = _structural_match(text)
    if structural is not None:
        intent, extracted = structural
        return OfflineResolution(
            matched=True,
            intent=intent,
            params={**default_params(intent), **extracted},
            similarity=1.0,
            confidence="high",
        )

    entries, vectors = _load_or_build_embeddings()
    model = _get_model()
    query_vec = model.encode([text], normalize_embeddings=True)[0]

    similarities = vectors @ query_vec
    best_idx = int(np.argmax(similarities))
    best_similarity = float(similarities[best_idx])
    best_entry = entries[best_idx]

    settings = get_settings()
    intent = next(i for i in load_intents() if i.intent_id == best_entry.intent_id)
    params = {**default_params(intent), **_extract_params(text, intent)}

    if best_similarity >= settings.offline_high_confidence_threshold:
        return OfflineResolution(
            matched=True,
            intent=intent,
            params=params,
            similarity=best_similarity,
            confidence="high",
        )

    if best_similarity >= settings.offline_low_confidence_threshold:
        return OfflineResolution(
            matched=True,
            intent=intent,
            params=params,
            similarity=best_similarity,
            confidence="medium",
            message=f"Did you mean: {intent.description}?",
        )

    return OfflineResolution(
        matched=False,
        intent=None,
        params={},
        similarity=best_similarity,
        confidence="none",
        message=(
            "I couldn't confidently match that to a known action while offline. "
            "Try rephrasing, or connect to the internet to use the AI assistant "
            "for more open-ended requests."
        ),
    )
