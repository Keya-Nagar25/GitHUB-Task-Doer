from unittest.mock import MagicMock

import pytest
from sqlmodel import Session, SQLModel, create_engine

from app.history.models import ActionLogEntry
from app.history.service import NotUndoableError, perform_undo, record_action, undo_strategy_for


@pytest.fixture
def db():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


def test_undo_strategy_looked_up_from_intent_catalog():
    assert undo_strategy_for("github_create_pr") == "api_delete"
    assert undo_strategy_for("push") == "not_undoable"
    assert undo_strategy_for("totally_unknown_action") == "not_undoable"


def test_record_action_persists_entry(db):
    entry = record_action(
        db,
        github_user_id=1,
        action="github_open_issue",
        params={"title": "bug", "body": ""},
        repo_owner="o",
        repo_name="r",
        post_state={"number": 7, "html_url": "https://github.com/o/r/issues/7"},
    )
    assert entry.id
    assert entry.undo_strategy == "api_delete"
    assert entry.undone is False
    assert db.get(ActionLogEntry, entry.id) is not None


def test_undo_create_pr_closes_it(db):
    entry = record_action(
        db, github_user_id=1, action="github_create_pr", params={},
        repo_owner="o", repo_name="r", post_state={"number": 5, "html_url": "x"},
    )
    fake_client = MagicMock()
    fake_client.close_pr.return_value = {"state": "closed"}

    result = perform_undo(db, entry, fake_client)

    fake_client.close_pr.assert_called_once_with("o", "r", 5)
    assert result == {"state": "closed"}
    assert entry.undone is True


def test_undo_fork_deletes_it(db):
    entry = record_action(
        db, github_user_id=1, action="github_fork", params={},
        repo_owner="o", repo_name="r", post_state={"owner": "keya", "name": "r"},
    )
    fake_client = MagicMock()

    result = perform_undo(db, entry, fake_client)

    fake_client.delete_repo.assert_called_once_with("keya", "r")
    assert result == {"deleted": "keya/r"}
    assert entry.undone is True


def test_cannot_undo_twice(db):
    entry = record_action(
        db, github_user_id=1, action="github_open_issue", params={},
        repo_owner="o", repo_name="r", post_state={"number": 1, "html_url": "x"},
    )
    fake_client = MagicMock()
    perform_undo(db, entry, fake_client)

    with pytest.raises(NotUndoableError):
        perform_undo(db, entry, fake_client)


def test_push_is_never_automatically_undoable(db):
    entry = record_action(
        db, github_user_id=1, action="push", params={"remote": "origin"},
        repo_owner="o", repo_name="r", post_state=None,
    )
    fake_client = MagicMock()

    with pytest.raises(NotUndoableError):
        perform_undo(db, entry, fake_client)

    fake_client.close_pr.assert_not_called()
    fake_client.close_issue.assert_not_called()
    fake_client.delete_repo.assert_not_called()
