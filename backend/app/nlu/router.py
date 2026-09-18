from dataclasses import dataclass

from app.nlu.offline_classifier import resolve_offline
from app.nlu.online_llm import resolve_online


@dataclass(frozen=True)
class RouterResolution:
    matched: bool
    action: str | None
    params: dict
    explanation: str | None
    destructive: bool
    confidence: str  # "medium" | "high" -- only meaningful when matched
    source: str  # "offline" | "online"
    matched_intent_id: str | None
    clarifying_question: str | None
    message: str | None  # shown to the user when not resolved outright


def resolve(text: str) -> RouterResolution:
    """Offline-first, online-fallback intent resolution.

    A high-confidence offline (structural or embedding) match is returned
    immediately -- no network call needed. Anything offline is unsure about
    (medium confidence, or no match at all) tries the online LLM path, which
    can understand far more open-ended phrasing. If the online path is
    unavailable (no API key, offline machine, network/API error) or itself
    doesn't confidently resolve, this falls back to whatever the offline path
    found -- a "did you mean X?" medium-confidence match, or an honest
    "couldn't resolve that" message. Never fabricates a match either path
    wasn't confident about.
    """
    offline = resolve_offline(text)

    if offline.matched and offline.confidence == "high":
        return _from_offline(offline)

    online = resolve_online(text)

    if online.matched:
        return RouterResolution(
            matched=True,
            action=online.action.value if online.action else None,
            params=online.params,
            explanation=online.explanation,
            destructive=online.destructive,
            confidence=online.confidence,
            source="online",
            matched_intent_id=None,
            clarifying_question=None,
            message=None,
        )

    if offline.matched:
        return _from_offline(offline)

    message = online.clarifying_question or offline.message
    return RouterResolution(
        matched=False,
        action=None,
        params={},
        explanation=None,
        destructive=False,
        confidence="medium",
        source="online" if online.clarifying_question else "offline",
        matched_intent_id=None,
        clarifying_question=None,
        message=message,
    )


def _from_offline(offline) -> RouterResolution:
    intent = offline.intent
    explanation = intent.description
    if intent.extra_warning:
        explanation = f"{explanation} {intent.extra_warning}"

    return RouterResolution(
        matched=True,
        action=intent.action,
        params=offline.params,
        explanation=explanation,
        destructive=intent.destructive,
        confidence=offline.confidence,
        source="offline",
        matched_intent_id=intent.intent_id,
        clarifying_question=offline.message if offline.confidence == "medium" else None,
        message=None,
    )
