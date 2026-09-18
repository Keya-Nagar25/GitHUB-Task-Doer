from sqlmodel import Session

from app.actions.github_client import GithubClient
from app.history.models import ActionLogEntry
from app.nlu.intent_catalog import load_intents

# action -> undo_strategy, from the shared intent catalog (intent-data/intents.yaml)
# is the source of truth; this just indexes it by action for quick lookup.
_UNDO_STRATEGY_BY_ACTION: dict[str, str] = {intent.action: intent.undo_strategy for intent in load_intents()}


class NotUndoableError(Exception):
    pass


def undo_strategy_for(action: str) -> str:
    return _UNDO_STRATEGY_BY_ACTION.get(action, "not_undoable")


def record_action(
    db: Session,
    *,
    github_user_id: int,
    action: str,
    params: dict,
    repo_owner: str,
    repo_name: str,
    post_state: dict | None,
) -> ActionLogEntry:
    entry = ActionLogEntry(
        github_user_id=github_user_id,
        action=action,
        params=params,
        repo_owner=repo_owner,
        repo_name=repo_name,
        post_state=post_state,
        undo_strategy=undo_strategy_for(action),
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry


def perform_undo(db: Session, entry: ActionLogEntry, client: GithubClient) -> dict:
    """Undo one previously executed GitHub-API action.

    Only handles the `api_delete` strategy (create_pr/open_issue/fork) --
    the only actions this milestone can execute in the first place. Other
    strategies (reset_soft, revert, recreate_branch, ...) apply to local
    working-tree actions the VS Code extension executes and are out of
    scope here; `manual_only`/`not_undoable` are deliberately never
    automated (see docs/architecture.md).
    """
    if entry.undone:
        raise NotUndoableError("This action has already been undone.")

    if entry.undo_strategy != "api_delete":
        raise NotUndoableError(
            f"'{entry.action}' can't be undone automatically here "
            f"(undo strategy: {entry.undo_strategy})."
        )

    if entry.action == "github_create_pr":
        number = entry.post_state["number"]
        result = client.close_pr(entry.repo_owner, entry.repo_name, number)
    elif entry.action == "github_open_issue":
        number = entry.post_state["number"]
        result = client.close_issue(entry.repo_owner, entry.repo_name, number)
    elif entry.action == "github_fork":
        fork_owner = entry.post_state["owner"]
        fork_repo = entry.post_state["name"]
        client.delete_repo(fork_owner, fork_repo)
        result = {"deleted": f"{fork_owner}/{fork_repo}"}
    else:
        raise NotUndoableError(f"No undo handler implemented yet for '{entry.action}'.")

    entry.undone = True
    db.add(entry)
    db.commit()
    return result
