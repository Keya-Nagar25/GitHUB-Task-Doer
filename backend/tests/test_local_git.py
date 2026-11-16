from unittest.mock import MagicMock, patch

import pytest

from app.actions.local_git import (
    LocalGitError,
    _scrub,
    current_branch,
    current_head_sha,
    ensure_workspace,
    reset_soft,
    run_action,
)
from app.actions.schema import ActionType


def _ok(stdout: str = ""):
    return MagicMock(returncode=0, stdout=stdout, stderr="")


def _fail(stderr: str):
    return MagicMock(returncode=1, stdout="", stderr=stderr)


def test_scrub_removes_raw_token_and_its_basic_encoding():
    text = "fatal: could not read Username for 'https://ghp_secrettoken@github.com'"
    scrubbed = _scrub(text, "ghp_secrettoken")
    assert "ghp_secrettoken" not in scrubbed


def test_clone_uses_auth_header_and_scrubs_error(tmp_path):
    workspace_root = tmp_path / "workspaces"
    with (
        patch("app.actions.local_git.get_settings") as mock_settings,
        patch("app.actions.local_git.subprocess.run", return_value=_fail("token abc123 was rejected")) as mock_run,
    ):
        mock_settings.return_value.git_workspace_root = str(workspace_root)
        mock_settings.return_value.git_command_timeout_seconds = 60

        with pytest.raises(LocalGitError) as exc_info:
            ensure_workspace(1, "o", "r", "abc123")

    call_args = mock_run.call_args
    cmd = call_args.args[0]
    assert cmd[0] == "git"
    assert cmd[1] == "-c"
    assert "AUTHORIZATION: basic" in cmd[2]
    assert cmd[3] == "clone"
    assert "abc123" not in str(exc_info.value)


def test_fetch_used_when_workspace_already_cloned(tmp_path):
    workspace_root = tmp_path / "workspaces"
    path = workspace_root / "1" / "o__r"
    (path / ".git").mkdir(parents=True)

    with (
        patch("app.actions.local_git.get_settings") as mock_settings,
        patch("app.actions.local_git.subprocess.run", return_value=_ok()) as mock_run,
    ):
        mock_settings.return_value.git_workspace_root = str(workspace_root)
        mock_settings.return_value.git_command_timeout_seconds = 60
        ensure_workspace(1, "o", "r", "tok")

    cmds = [call.args[0] for call in mock_run.call_args_list]
    assert "fetch" in cmds[0]
    # ...then the checked-out branch is fast-forwarded to what was fetched.
    assert cmds[1] == ["git", "merge", "--ff-only", "@{u}"]


def test_fast_forward_failure_does_not_fail_workspace(tmp_path):
    # Diverged branch / no upstream: the fast-forward is skipped, not an error.
    workspace_root = tmp_path / "workspaces"
    path = workspace_root / "1" / "o__r"
    (path / ".git").mkdir(parents=True)

    with (
        patch("app.actions.local_git.get_settings") as mock_settings,
        patch(
            "app.actions.local_git.subprocess.run",
            side_effect=[_ok(), _fail("fatal: Not possible to fast-forward, aborting.")],
        ),
    ):
        mock_settings.return_value.git_workspace_root = str(workspace_root)
        mock_settings.return_value.git_command_timeout_seconds = 60
        assert ensure_workspace(1, "o", "r", "tok") == path


def test_current_head_sha_and_branch_run_expected_commands(tmp_path):
    with (
        patch("app.actions.local_git.get_settings") as mock_settings,
        patch("app.actions.local_git.subprocess.run", return_value=_ok("abc123\n")) as mock_run,
    ):
        mock_settings.return_value.git_command_timeout_seconds = 60
        sha = current_head_sha(tmp_path)
    assert sha == "abc123"
    assert mock_run.call_args.args[0] == ["git", "rev-parse", "HEAD"]

    with (
        patch("app.actions.local_git.get_settings") as mock_settings,
        patch("app.actions.local_git.subprocess.run", return_value=_ok("main\n")) as mock_run,
    ):
        mock_settings.return_value.git_command_timeout_seconds = 60
        branch = current_branch(tmp_path)
    assert branch == "main"


def test_run_action_commit_builds_correct_command(tmp_path):
    with (
        patch("app.actions.local_git.get_settings") as mock_settings,
        patch("app.actions.local_git.subprocess.run", return_value=_ok()) as mock_run,
    ):
        mock_settings.return_value.git_command_timeout_seconds = 60
        run_action(1, "o", "r", ActionType.COMMIT, {"message": "fix bug"}, tmp_path, "tok")

    assert mock_run.call_args.args[0] == ["git", "commit", "-m", "fix bug"]


def test_run_action_push_with_force_includes_auth_and_flag(tmp_path):
    with (
        patch("app.actions.local_git.get_settings") as mock_settings,
        patch("app.actions.local_git.subprocess.run", return_value=_ok()) as mock_run,
    ):
        mock_settings.return_value.git_command_timeout_seconds = 60
        run_action(
            1, "o", "r", ActionType.PUSH,
            {"remote": "origin", "branch": "main", "force": True}, tmp_path, "tok",
        )

    cmd = mock_run.call_args.args[0]
    assert cmd[0:2] == ["git", "-c"]
    assert cmd[3:] == ["push", "origin", "main", "--force"]


def test_run_action_add_without_paths_defaults_to_all(tmp_path):
    with (
        patch("app.actions.local_git.get_settings") as mock_settings,
        patch("app.actions.local_git.subprocess.run", return_value=_ok()) as mock_run,
    ):
        mock_settings.return_value.git_command_timeout_seconds = 60
        run_action(1, "o", "r", ActionType.ADD, {}, tmp_path, "tok")

    assert mock_run.call_args.args[0] == ["git", "add", "."]


def test_reset_soft_uses_recorded_sha(tmp_path):
    with (
        patch("app.actions.local_git.get_settings") as mock_settings,
        patch("app.actions.local_git.subprocess.run", return_value=_ok()) as mock_run,
    ):
        mock_settings.return_value.git_command_timeout_seconds = 60
        reset_soft(tmp_path, "deadbeef")

    assert mock_run.call_args.args[0] == ["git", "reset", "--soft", "deadbeef"]


def test_run_action_clone_runs_no_extra_git_command(tmp_path):
    # The clone itself already happened in ensure_workspace(); run_action just reports it.
    with patch("app.actions.local_git.subprocess.run") as mock_run:
        output = run_action(1, "o", "r", ActionType.CLONE, {}, tmp_path, "tok")

    mock_run.assert_not_called()
    assert "o/r" in output


def test_run_action_commit_is_authored_as_logged_in_user(tmp_path):
    with (
        patch("app.actions.local_git.get_settings") as mock_settings,
        patch("app.actions.local_git.subprocess.run", return_value=_ok()) as mock_run,
    ):
        mock_settings.return_value.git_command_timeout_seconds = 60
        run_action(1, "o", "r", ActionType.COMMIT, {"message": "fix bug"}, tmp_path, "tok", github_login="octocat")

    assert mock_run.call_args.args[0] == [
        "git",
        "-c", "user.name=octocat",
        "-c", "user.email=1+octocat@users.noreply.github.com",
        "commit", "-m", "fix bug",
    ]


def test_run_action_merge_is_authored_as_logged_in_user(tmp_path):
    with (
        patch("app.actions.local_git.get_settings") as mock_settings,
        patch("app.actions.local_git.subprocess.run", return_value=_ok()) as mock_run,
    ):
        mock_settings.return_value.git_command_timeout_seconds = 60
        run_action(1, "o", "r", ActionType.MERGE, {"ref": "feature"}, tmp_path, "tok", github_login="octocat")

    cmd = mock_run.call_args.args[0]
    assert "user.name=octocat" in cmd
    assert cmd[-2:] == ["merge", "feature"]
