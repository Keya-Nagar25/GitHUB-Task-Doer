from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel

from app.actions.schema import ResolvedAction
from app.actions.validator import InvalidActionError, validate_action
from app.nlu.offline_classifier import resolve_offline

router = APIRouter()


class ResolveRequest(BaseModel):
    text: str


class ResolveResponse(BaseModel):
    status: Literal["resolved", "needs_clarification", "unresolved"]
    resolved_action: ResolvedAction | None = None
    message: str | None = None


@router.post("/resolve", response_model=ResolveResponse)
def resolve(request: ResolveRequest) -> ResolveResponse:
    offline = resolve_offline(request.text)

    if not offline.matched or offline.intent is None:
        return ResolveResponse(status="unresolved", message=offline.message)

    intent = offline.intent
    explanation = intent.description
    if intent.extra_warning:
        explanation = f"{explanation} {intent.extra_warning}"

    try:
        resolved = validate_action(
            action=intent.action,
            params=offline.params,
            explanation=explanation,
            destructive=intent.destructive,
            confidence=offline.confidence,
            source="offline",
            matched_intent_id=intent.intent_id,
            clarifying_question=offline.message if offline.confidence == "medium" else None,
        )
    except InvalidActionError:
        missing = set(intent.param_schema.keys()) - set(offline.params.keys())
        return ResolveResponse(
            status="needs_clarification",
            message=(
                f"I think you want to: {intent.description}. "
                f"I still need: {', '.join(sorted(missing)) or 'more details'}."
            ),
        )

    return ResolveResponse(status="resolved", resolved_action=resolved)
