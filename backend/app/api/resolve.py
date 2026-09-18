from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel

from app.actions.schema import ACTION_PARAM_MODELS, ActionType, ResolvedAction
from app.actions.validator import InvalidActionError, validate_action
from app.nlu.router import resolve as resolve_intent

router = APIRouter()


class ResolveRequest(BaseModel):
    text: str


class ResolveResponse(BaseModel):
    status: Literal["resolved", "needs_clarification", "unresolved"]
    resolved_action: ResolvedAction | None = None
    message: str | None = None


def _missing_required_params(action: ActionType, params: dict) -> set[str]:
    model = ACTION_PARAM_MODELS[action]
    required = {name for name, field in model.model_fields.items() if field.is_required()}
    return required - set(params.keys())


@router.post("/resolve", response_model=ResolveResponse)
def resolve(request: ResolveRequest) -> ResolveResponse:
    outcome = resolve_intent(request.text)

    if not outcome.matched or outcome.action is None:
        return ResolveResponse(status="unresolved", message=outcome.message)

    try:
        resolved = validate_action(
            action=outcome.action,
            params=outcome.params,
            explanation=outcome.explanation or "",
            destructive=outcome.destructive,
            confidence=outcome.confidence,
            source=outcome.source,
            matched_intent_id=outcome.matched_intent_id,
            clarifying_question=outcome.clarifying_question,
        )
    except InvalidActionError:
        missing = _missing_required_params(ActionType(outcome.action), outcome.params)
        detail = f"I still need: {', '.join(sorted(missing))}." if missing else "Some details didn't look right."
        return ResolveResponse(
            status="needs_clarification",
            message=f"I think you want to: {outcome.explanation}. {detail}",
        )

    return ResolveResponse(status="resolved", resolved_action=resolved)
