from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session

from app.actions.github_client import GithubApiError, GithubClient
from app.actions.local_git import LocalGitError, current_head_sha, ensure_workspace, run_action
from app.actions.schema import GITHUB_API_ACTIONS, ActionType, RepoRef, ResolvedAction
from app.actions.validator import InvalidActionError, validate_action
from app.auth.crypto import decrypt_token
from app.auth.deps import get_current_session
from app.auth.models import UserSession
from app.db import get_db_session
from app.history.service import record_action

router = APIRouter()


class ExecuteRequest(BaseModel):
    resolved_action: ResolvedAction
    repo: RepoRef
    # Echoes the user's explicit "Confirm & Run" click -- the API refuses to
    # execute anything without it, so there is no code path that runs an
    # action without a rendered confirmation screen in front of it.
    confirmed: bool = False


class ExecuteResponse(BaseModel):
    status: str = "executed"
    result: dict
    action_log_id: str


@router.post("/execute", response_model=ExecuteResponse)
def execute(
    request: ExecuteRequest,
    session: UserSession = Depends(get_current_session),
    db: Session = Depends(get_db_session),
) -> ExecuteResponse:
    if not request.confirmed:
        raise HTTPException(status_code=400, detail="This action was not confirmed by the user")

    # Re-validate server-side -- never trust the echoed resolved_action as-is,
    # it round-tripped through the client and could have been tampered with.
    try:
        resolved = validate_action(
            action=request.resolved_action.action.value,
            params=request.resolved_action.params,
            explanation=request.resolved_action.explanation,
            destructive=request.resolved_action.destructive,
            confidence=request.resolved_action.confidence,
            source=request.resolved_action.source,
            matched_intent_id=request.resolved_action.matched_intent_id,
            clarifying_question=request.resolved_action.clarifying_question,
        )
    except InvalidActionError as exc:
        raise HTTPException(status_code=400, detail="Could not safely re-validate this action") from exc

    access_token = decrypt_token(session.encrypted_access_token)

    if resolved.action in GITHUB_API_ACTIONS:
        client = GithubClient(access_token=access_token)
        try:
            result, post_state = _execute_github_action(client, resolved.action, resolved.params, request.repo)
        except GithubApiError as exc:
            raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
        pre_state = None
    else:
        try:
            result, pre_state, post_state = _execute_local_git_action(
                session.github_user_id, request.repo, resolved.action, resolved.params, access_token
            )
        except LocalGitError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    entry = record_action(
        db,
        github_user_id=session.github_user_id,
        action=resolved.action.value,
        params=resolved.params,
        repo_owner=request.repo.owner,
        repo_name=request.repo.repo,
        pre_state=pre_state,
        post_state=post_state,
    )

    return ExecuteResponse(result=result, action_log_id=entry.id)


def _execute_github_action(
    client: GithubClient, action: ActionType, params: dict, repo: RepoRef
) -> tuple[dict, dict]:
    if action is ActionType.GITHUB_CREATE_PR:
        result = client.create_pr(repo.owner, repo.repo, title=params["title"], head=params["head"], base=params["base"])
        return result, {"number": result["number"], "html_url": result["html_url"]}

    if action is ActionType.GITHUB_OPEN_ISSUE:
        result = client.open_issue(repo.owner, repo.repo, title=params["title"], body=params.get("body", ""))
        return result, {"number": result["number"], "html_url": result["html_url"]}

    if action is ActionType.GITHUB_FORK:
        target_owner = params.get("owner") or repo.owner
        target_repo = params.get("repo") or repo.repo
        result = client.fork(target_owner, target_repo)
        return result, {"owner": result["owner"]["login"], "name": result["name"], "html_url": result["html_url"]}

    raise HTTPException(status_code=400, detail=f"No execution handler for '{action.value}'")


def _execute_local_git_action(
    github_user_id: int, repo: RepoRef, action: ActionType, params: dict, access_token: str
) -> tuple[dict, dict, dict]:
    path = ensure_workspace(github_user_id, repo.owner, repo.repo, access_token)
    pre_state = {"head_sha": current_head_sha(path)}

    output = run_action(github_user_id, repo.owner, repo.repo, action, params, path, access_token)

    post_state = {"head_sha": current_head_sha(path)}
    return {"output": output, "head_sha": post_state["head_sha"]}, pre_state, post_state
