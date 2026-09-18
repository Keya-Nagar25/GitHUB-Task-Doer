from dataclasses import dataclass
from typing import Literal

import anthropic
from pydantic import BaseModel

from app.actions.schema import ActionType
from app.config import get_settings
from app.nlu.intent_catalog import load_intents

_MODEL = "claude-opus-5"


class _LLMActionResponse(BaseModel):
    action: ActionType | None = None
    params: dict[str, str] = {}
    explanation: str = ""
    destructive: bool = False
    confidence: Literal["medium", "high"] = "high"
    clarifying_question: str | None = None


@dataclass(frozen=True)
class OnlineResolution:
    matched: bool
    action: ActionType | None
    params: dict
    explanation: str
    destructive: bool
    confidence: str
    clarifying_question: str | None = None
    error: str | None = None  # set when the call itself failed (auth/network/etc.)


def _build_system_prompt() -> str:
    lines = [
        "You translate a beginner's plain-English request about Git/GitHub into "
        "exactly one action from a fixed catalog, for an assistant that always shows "
        "the user the resulting command and a plain-English explanation before it "
        "ever runs anything. You never cause anything to execute yourself.",
        "",
        "Rules:",
        "- Only ever choose an action from the catalog below. Never invent an action.",
        "- If the request is ambiguous, ask about something you can't safely infer, "
        "or doesn't match any known action, leave `action` null and set "
        "`clarifying_question` instead. Never guess.",
        "- `params` must only contain values you can confidently read from the "
        "user's request. Omit a param entirely rather than inventing one.",
        "- Set `destructive` to true for anything that could discard committed or "
        "uncommitted work (e.g. a hard reset, a force push).",
        "- `explanation` must be one plain-English sentence describing what the "
        "action will do, written for a beginner, not a git command reference.",
        "",
        "Catalog of allowed actions (action name, expected params -- a literal "
        "value means always use exactly that value, a type name means read it "
        "from the user's request):",
    ]
    for intent in load_intents():
        lines.append(f"- action={intent.action}: {intent.description}. params={intent.param_schema}")
    return "\n".join(lines)


def resolve_online(text: str) -> OnlineResolution:
    """Resolve English to an action via the Claude API. Requires network + API key.

    Never raises for expected failure modes (missing key, network error, API
    error) -- returns a resolution with `error` set so the router can fall back
    to the offline path instead of the request failing outright.
    """
    settings = get_settings()
    if not settings.anthropic_api_key:
        return OnlineResolution(
            matched=False,
            action=None,
            params={},
            explanation="",
            destructive=False,
            confidence="medium",
            error="no_api_key",
        )

    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)

    try:
        response = client.messages.parse(
            model=_MODEL,
            max_tokens=1024,
            system=_build_system_prompt(),
            messages=[{"role": "user", "content": text}],
            output_format=_LLMActionResponse,
        )
    except anthropic.AuthenticationError:
        return OnlineResolution(
            matched=False, action=None, params={}, explanation="", destructive=False,
            confidence="medium", error="authentication_error",
        )
    except anthropic.RateLimitError:
        return OnlineResolution(
            matched=False, action=None, params={}, explanation="", destructive=False,
            confidence="medium", error="rate_limited",
        )
    except anthropic.APIConnectionError:
        return OnlineResolution(
            matched=False, action=None, params={}, explanation="", destructive=False,
            confidence="medium", error="connection_error",
        )
    except anthropic.APIStatusError as exc:
        return OnlineResolution(
            matched=False, action=None, params={}, explanation="", destructive=False,
            confidence="medium", error=f"api_error_{exc.status_code}",
        )

    parsed = response.parsed_output

    return OnlineResolution(
        matched=parsed.action is not None,
        action=parsed.action,
        params=parsed.params,
        explanation=parsed.explanation,
        destructive=parsed.destructive,
        confidence=parsed.confidence,
        clarifying_question=parsed.clarifying_question,
    )
