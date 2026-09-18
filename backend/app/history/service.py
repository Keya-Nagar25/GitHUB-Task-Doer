from sqlmodel import Session

from app.actions.github_client import GithubClient
from app.actions.local_git import delete_branch, ensure_workspace, reset_soft
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
    pre_state: dict | None = None,
    post_state: dict | None,
) -> ActionLogEntry:
    entry = ActionLogEntry(
        github_user_id=github_user_id,
        action=action,
        params=params,
        repo_owner=repo_owner,
        repo_name=repo_name,
        pre_state=pre_state,
        post_state=post_state,
        undo_strategy=undo_strategy_for(action),
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry


def perform_undo(
    db: Session, entry: ActionLogEntry, *, github_client: GithubClient, access_token: str
) -> dict:
    """Undo one previously executed action.

    Only strategies with an automated handler here can be undone at all --
    `manual_only`/`not_undoable` are deliberately never automated (push and
    a hard reset chief among them: automating undo of shared/destroyed
    history risks doing more damage, not less). See docs/architecture.md.
    """
    if entry.undone:
        raise NotUndoableError("This action has already been undone.")

    if entry.undo_strategy == "api_delete":
        result = _undo_api_delete(entry, github_client)
    elif entry.undo_strategy == "reset_soft":
        result = _undo_reset_soft(entry, access_token)
    elif entry.undo_strategy == "delete_branch":
        result = _undo_delete_branch(entry, access_token)
    else:
        raise NotUndoableError(
            f"'{entry.action}' can't be undone automatically here "
            f"(undo strategy: {entry.undo_strategy})."
        )

    entry.undone = True
    db.add(entry)
    db.commit()
    return result


def _undo_api_delete(entry: ActionLogEntry, github_client: GithubClient) -> dict:
    if entry.action == "github_create_pr":
        number = entry.post_state["number"]
        return github_client.close_pr(entry.repo_owner, entry.repo_name, number)
    if entry.action == "github_open_issue":
        number = entry.post_state["number"]
        return github_client.close_issue(entry.repo_owner, entry.repo_name, number)
    if entry.action == "github_fork":
        fork_owner = entry.post_state["owner"]
        fork_repo = entry.post_state["name"]
        github_client.delete_repo(fork_owner, fork_repo)
        return {"deleted": f"{fork_owner}/{fork_repo}"}
    raise NotUndoableError(f"No undo handler implemented yet for '{entry.action}'.")


def _undo_reset_soft(entry: ActionLogEntry, access_token: str) -> dict:
    if not entry.pre_state or "head_sha" not in entry.pre_state:
        raise NotUndoableError("No recorded prior state to undo to.")
    path = ensure_workspace(entry.github_user_id, entry.repo_owner, entry.repo_name, access_token)
    output = reset_soft(path, entry.pre_state["head_sha"])
    return {"output": output, "reset_to": entry.pre_state["head_sha"]}


def _undo_delete_branch(entry: ActionLogEntry, access_token: str) -> dict:
    name = entry.params.get("name")
    if not name:
        raise NotUndoableError("No branch name recorded to undo.")
    path = ensure_workspace(entry.github_user_id, entry.repo_owner, entry.repo_name, access_token)
    output = delete_branch(path, name)
    return {"output": output, "deleted_branch": name}
