from unittest.mock import patch

from app.actions.schema import ActionType
from app.nlu.intent_catalog import get_intent
from app.nlu.offline_classifier import OfflineResolution
from app.nlu.online_llm import OnlineResolution
from app.nlu.router import resolve


def test_high_confidence_offline_match_skips_online_call():
    offline = OfflineResolution(
        matched=True,
        intent=get_intent("git.commit"),
        params={"message": "hi"},
        similarity=1.0,
        confidence="high",
    )
    with (
        patch("app.nlu.router.resolve_offline", return_value=offline),
        patch("app.nlu.router.resolve_online") as mock_online,
    ):
        result = resolve("commit my changes")

    mock_online.assert_not_called()
    assert result.matched is True
    assert result.source == "offline"
    assert result.action == "commit"


def test_medium_confidence_offline_prefers_successful_online_match():
    offline = OfflineResolution(
        matched=True,
        intent=get_intent("git.stash"),
        params={},
        similarity=0.6,
        confidence="medium",
        message="Did you mean: Temporarily shelve uncommitted changes?",
    )
    online = OnlineResolution(
        matched=True,
        action=ActionType.COMMIT,
        params={"message": "wip"},
        explanation="Commit staged changes with your message",
        destructive=False,
        confidence="high",
    )
    with (
        patch("app.nlu.router.resolve_offline", return_value=offline),
        patch("app.nlu.router.resolve_online", return_value=online),
    ):
        result = resolve("please commit this with message wip")

    assert result.matched is True
    assert result.source == "online"
    assert result.action == "commit"


def test_online_unavailable_falls_back_to_offline_medium_confidence():
    offline = OfflineResolution(
        matched=True,
        intent=get_intent("git.stash"),
        params={},
        similarity=0.6,
        confidence="medium",
        message="Did you mean: Temporarily shelve uncommitted changes?",
    )
    online = OnlineResolution(
        matched=False, action=None, params={}, explanation="", destructive=False,
        confidence="medium", error="no_api_key",
    )
    with (
        patch("app.nlu.router.resolve_offline", return_value=offline),
        patch("app.nlu.router.resolve_online", return_value=online),
    ):
        result = resolve("please commit this for me")

    assert result.matched is True
    assert result.source == "offline"
    assert result.action == "stash"
    assert result.clarifying_question is not None


def test_nothing_matches_returns_unresolved_message():
    offline = OfflineResolution(
        matched=False, intent=None, params={}, similarity=0.1, confidence="none",
        message="I couldn't confidently match that offline.",
    )
    online = OnlineResolution(
        matched=False, action=None, params={}, explanation="", destructive=False,
        confidence="medium", error="no_api_key",
    )
    with (
        patch("app.nlu.router.resolve_offline", return_value=offline),
        patch("app.nlu.router.resolve_online", return_value=online),
    ):
        result = resolve("what is the weather today")

    assert result.matched is False
    assert result.message == "I couldn't confidently match that offline."
