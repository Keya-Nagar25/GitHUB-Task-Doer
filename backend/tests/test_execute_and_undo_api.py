from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from app.actions.schema import ActionType
from app.auth.crypto import encrypt_token
from app.auth.deps import get_current_session
from app.auth.models import UserSession
from app.db import get_db_session
from app.main import app


@pytest.fixture
def test_db():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    SQLModel.metadata.create_all(engine)
    return engine


@pytest.fixture
def client(test_db):
    fake_session = UserSession(
        token="test-session-token",
        github_user_id=1,
        github_login="octocat",
        encrypted_access_token=encrypt_token("fake-gh-token"),
    )

    def override_db():
        with Session(test_db) as session:
            yield session

    def override_current_session():
        return fake_session

    app.dependency_overrides[get_db_session] = override_db
    app.dependency_overrides[get_current_session] = override_current_session

    with TestClient(app) as c:
        yield c

    app.dependency_overrides.clear()


def _resolved_action(action="github_open_issue", params=None):
    return {
        "action": action,
        "params": params or {"title": "bug", "body": "it's broken"},
        "explanation": "Open an issue on GitHub",
        "destructive": False,
        "confidence": "high",
        "source": "offline",
    }


def test_execute_requires_confirmation(client):
    response = client.post(
        "/execute",
        json={
            "resolved_action": _resolved_action(),
            "repo": {"owner": "o", "repo": "r"},
            "confirmed": False,
        },
    )
    assert response.status_code == 400


def test_execute_commit_runs_via_local_git_workspace(client):
    with (
        patch("app.api.execute.ensure_workspace", return_value="/workspace/o__r") as mock_ws,
        patch("app.api.execute.current_head_sha", side_effect=["sha-before", "sha-after"]),
        patch("app.api.execute.run_action", return_value="[main abc1234] fix bug") as mock_run,
    ):
        response = client.post(
            "/execute",
            json={
                "resolved_action": _resolved_action(action="commit", params={"message": "fix bug"}),
                "repo": {"owner": "o", "repo": "r"},
                "confirmed": True,
            },
        )

    assert response.status_code == 200
    body = response.json()
    assert body["result"]["head_sha"] == "sha-after"
    mock_ws.assert_called_once_with(1, "o", "r", "fake-gh-token")
    mock_run.assert_called_once()
    assert mock_run.call_args.args[0:4] == (1, "o", "r", ActionType.COMMIT)


def test_execute_open_issue_then_undo(client):
    fake_github_client = MagicMock()
    fake_github_client.open_issue.return_value = {"number": 9, "html_url": "https://github.com/o/r/issues/9"}
    fake_github_client.close_issue.return_value = {"state": "closed"}

    with patch("app.api.execute.GithubClient", return_value=fake_github_client):
        exec_response = client.post(
            "/execute",
            json={
                "resolved_action": _resolved_action(),
                "repo": {"owner": "o", "repo": "r"},
                "confirmed": True,
            },
        )
    assert exec_response.status_code == 200
    body = exec_response.json()
    assert body["result"]["number"] == 9
    action_log_id = body["action_log_id"]

    with patch("app.api.undo.GithubClient", return_value=fake_github_client):
        undo_response = client.post(f"/undo/{action_log_id}")
    assert undo_response.status_code == 200
    fake_github_client.close_issue.assert_called_once_with("o", "r", 9)

    with patch("app.api.undo.GithubClient", return_value=fake_github_client):
        second_undo = client.post(f"/undo/{action_log_id}")
    assert second_undo.status_code == 400
