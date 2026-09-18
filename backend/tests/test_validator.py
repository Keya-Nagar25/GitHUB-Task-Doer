import pytest

from app.actions.validator import InvalidActionError, validate_action


def test_valid_commit_action_passes():
    resolved = validate_action(
        action="commit",
        params={"message": "fix bug"},
        explanation="Commit staged changes",
        destructive=False,
        confidence="high",
        source="offline",
    )
    assert resolved.action.value == "commit"
    assert resolved.params["message"] == "fix bug"
    assert resolved.requires_double_confirmation is False


def test_unknown_action_is_rejected():
    with pytest.raises(InvalidActionError):
        validate_action(
            action="rm_rf_repo",
            params={},
            explanation="nope",
            destructive=True,
            confidence="high",
            source="offline",
        )


def test_missing_required_param_is_rejected():
    with pytest.raises(InvalidActionError):
        validate_action(
            action="commit",
            params={},
            explanation="Commit staged changes",
            destructive=False,
            confidence="high",
            source="offline",
        )


def test_ref_with_shell_metacharacters_is_rejected():
    with pytest.raises(InvalidActionError):
        validate_action(
            action="checkout",
            params={"ref": "main; rm -rf /"},
            explanation="Switch branch",
            destructive=False,
            confidence="high",
            source="offline",
        )


def test_reset_hard_requires_double_confirmation():
    resolved = validate_action(
        action="reset",
        params={"mode": "hard", "target": "HEAD~1"},
        explanation="Discard changes",
        destructive=True,
        confidence="high",
        source="offline",
    )
    assert resolved.requires_double_confirmation is True


def test_reset_soft_does_not_require_double_confirmation():
    resolved = validate_action(
        action="reset",
        params={"mode": "soft", "target": "HEAD~1"},
        explanation="Undo last commit",
        destructive=False,
        confidence="high",
        source="offline",
    )
    assert resolved.requires_double_confirmation is False
