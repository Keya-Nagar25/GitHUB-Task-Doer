from unittest.mock import MagicMock, patch

import anthropic
import httpx2

from app.actions.schema import ActionType
from app.config import Settings
from app.nlu.online_llm import _LLMActionResponse, resolve_online


def _fake_settings(key: str | None) -> Settings:
    return Settings(anthropic_api_key=key)


def _fake_request() -> httpx2.Request:
    return httpx2.Request("POST", "https://api.anthropic.com/v1/messages")


def test_no_api_key_returns_unmatched_with_error():
    with patch("app.nlu.online_llm.get_settings", return_value=_fake_settings(None)):
        result = resolve_online("commit my changes")
    assert result.matched is False
    assert result.error == "no_api_key"


def test_successful_resolution_maps_parsed_output():
    fake_parsed = _LLMActionResponse(
        action=ActionType.COMMIT,
        params={"message": "fix login bug"},
        explanation="Commit staged changes with your message",
        destructive=False,
        confidence="high",
    )
    fake_response = MagicMock(parsed_output=fake_parsed)

    with (
        patch("app.nlu.online_llm.get_settings", return_value=_fake_settings("sk-fake")),
        patch("app.nlu.online_llm.anthropic.Anthropic") as mock_client_cls,
    ):
        mock_client_cls.return_value.messages.parse.return_value = fake_response
        result = resolve_online("please save my work, message: fix login bug")

    assert result.matched is True
    assert result.action == ActionType.COMMIT
    assert result.params == {"message": "fix login bug"}
    assert result.error is None


def test_ambiguous_request_returns_clarifying_question_not_a_guess():
    fake_parsed = _LLMActionResponse(
        action=None,
        clarifying_question="Do you want to undo your last commit or discard all changes?",
    )
    fake_response = MagicMock(parsed_output=fake_parsed)

    with (
        patch("app.nlu.online_llm.get_settings", return_value=_fake_settings("sk-fake")),
        patch("app.nlu.online_llm.anthropic.Anthropic") as mock_client_cls,
    ):
        mock_client_cls.return_value.messages.parse.return_value = fake_response
        result = resolve_online("undo everything")

    assert result.matched is False
    assert result.action is None
    assert result.clarifying_question is not None


def test_authentication_error_is_caught_not_raised():
    request = _fake_request()
    response = httpx2.Response(status_code=401, request=request)
    error = anthropic.AuthenticationError("bad key", response=response, body=None)

    with (
        patch("app.nlu.online_llm.get_settings", return_value=_fake_settings("sk-fake")),
        patch("app.nlu.online_llm.anthropic.Anthropic") as mock_client_cls,
    ):
        mock_client_cls.return_value.messages.parse.side_effect = error
        result = resolve_online("commit my changes")

    assert result.matched is False
    assert result.error == "authentication_error"


def test_connection_error_is_caught_not_raised():
    error = anthropic.APIConnectionError(request=_fake_request())

    with (
        patch("app.nlu.online_llm.get_settings", return_value=_fake_settings("sk-fake")),
        patch("app.nlu.online_llm.anthropic.Anthropic") as mock_client_cls,
    ):
        mock_client_cls.return_value.messages.parse.side_effect = error
        result = resolve_online("commit my changes")

    assert result.matched is False
    assert result.error == "connection_error"
