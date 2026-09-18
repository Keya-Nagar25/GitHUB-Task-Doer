from pydantic import ValidationError

from app.actions.schema import ACTION_PARAM_MODELS, ActionType, ResolvedAction


class InvalidActionError(Exception):
    """Raised whenever a proposed action fails validation.

    This must always be handled by returning a generic "couldn't resolve that
    safely" response to the caller -- never partially executed, never leaked
    back the raw underlying error detail to the execution layer.
    """


def validate_action(
    *,
    action: str,
    params: dict,
    explanation: str,
    destructive: bool,
    confidence: str,
    source: str,
    matched_intent_id: str | None = None,
    clarifying_question: str | None = None,
) -> ResolvedAction:
    """The single choke point every NLU resolution (offline or online) must pass
    through before it is shown to the user or reaches the execution engine.

    Re-validates the action name against the server-side ActionType enum (never
    trusts the caller's string) and validates params against that action's
    strict Pydantic model, so no unvalidated data can reach a subprocess or API
    call downstream.
    """
    try:
        action_type = ActionType(action)
    except ValueError as exc:
        raise InvalidActionError(f"Unknown action: {action!r}") from exc

    param_model = ACTION_PARAM_MODELS[action_type]
    try:
        validated_params = param_model.model_validate(params)
    except ValidationError as exc:
        raise InvalidActionError(f"Invalid params for action {action_type}: {exc}") from exc

    requires_double_confirmation = _requires_double_confirmation(action_type, validated_params.model_dump())

    return ResolvedAction(
        action=action_type,
        params=validated_params.model_dump(),
        explanation=explanation,
        destructive=destructive,
        requires_double_confirmation=requires_double_confirmation,
        confidence=confidence,
        matched_intent_id=matched_intent_id,
        clarifying_question=clarifying_question,
        source=source,
    )


def _requires_double_confirmation(action_type: ActionType, params: dict) -> bool:
    if action_type is ActionType.RESET and params.get("mode") == "hard":
        return True
    if action_type is ActionType.PUSH and params.get("force"):
        return True
    return False
