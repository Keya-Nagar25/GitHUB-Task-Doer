import base64
import subprocess
import threading
from pathlib import Path

from app.actions.schema import ActionType
from app.config import get_settings

_locks_guard = threading.Lock()
_workspace_locks: dict[str, threading.Lock] = {}


class LocalGitError(Exception):
    pass


def _workspace_lock(github_user_id: int, owner: str, repo: str) -> threading.Lock:
    key = f"{github_user_id}:{owner}/{repo}"
    with _locks_guard:
        if key not in _workspace_locks:
            _workspace_locks[key] = threading.Lock()
        return _workspace_locks[key]


def workspace_path(github_user_id: int, owner: str, repo: str) -> Path:
    root = Path(get_settings().git_workspace_root).resolve()
    # owner/repo are already validated as GitRef (no "..", no path separators
    # beyond what GitRef allows) by the time they reach here -- see
    # actions/schema.py -- so this can't escape the workspace root.
    return root / str(github_user_id) / f"{owner}__{repo}"


def _auth_header(access_token: str) -> str:
    basic = base64.b64encode(f"x-access-token:{access_token}".encode()).decode()
    return f"AUTHORIZATION: basic {basic}"


def _scrub(text: str, access_token: str | None) -> str:
    if not access_token:
        return text
    scrubbed = text.replace(access_token, "***")
    basic = base64.b64encode(f"x-access-token:{access_token}".encode()).decode()
    return scrubbed.replace(basic, "***")


def _run(args: list[str], *, cwd: Path, access_token: str | None = None, needs_auth: bool = False) -> str:
    cmd = ["git"]
    if needs_auth:
        if not access_token:
            raise LocalGitError("This action needs to reach GitHub but no access token is available.")
        # Passed as a one-off `-c` override, not written to the clone's config,
        # so the token never lands in `.git/config` or `git remote -v` output.
        cmd += ["-c", _auth_header(access_token)]
    cmd += args

    try:
        result = subprocess.run(
            cmd,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=get_settings().git_command_timeout_seconds,
        )
    except subprocess.TimeoutExpired as exc:
        raise LocalGitError(f"git {' '.join(args)} timed out") from exc

    if result.returncode != 0:
        detail = _scrub((result.stderr or result.stdout or "").strip(), access_token)
        raise LocalGitError(detail or f"git {' '.join(args)} failed with exit code {result.returncode}")
    return result.stdout


def ensure_workspace(github_user_id: int, owner: str, repo: str, access_token: str) -> Path:
    """Clone the repo server-side if this is the first time this user has
    touched it here, otherwise fetch to catch up. This workspace is a fresh
    copy pulled from GitHub -- not the user's own machine -- so it only ever
    reflects what's already on GitHub, not uncommitted local work.
    """
    path = workspace_path(github_user_id, owner, repo)
    with _workspace_lock(github_user_id, owner, repo):
        if not (path / ".git").exists():
            path.mkdir(parents=True, exist_ok=True)
            clone_url = f"https://github.com/{owner}/{repo}.git"
            _run(["clone", clone_url, "."], cwd=path, access_token=access_token, needs_auth=True)
        else:
            _run(["fetch", "origin"], cwd=path, access_token=access_token, needs_auth=True)
    return path


def current_head_sha(path: Path) -> str:
    return _run(["rev-parse", "HEAD"], cwd=path).strip()


def current_branch(path: Path) -> str:
    return _run(["rev-parse", "--abbrev-ref", "HEAD"], cwd=path).strip()


def run_action(
    github_user_id: int, owner: str, repo: str, action: ActionType, params: dict, path: Path, access_token: str
) -> str:
    """Run one whitelisted git action against an already-prepared workspace.

    `params` has already passed through actions/validator.py by the time it
    gets here -- refs are charset-restricted (see schema.GitRef), so this
    never builds a shell string and never runs with shell=True.
    """
    with _workspace_lock(github_user_id, owner, repo):
        if action is ActionType.ADD:
            paths = params.get("paths") or ["."]
            return _run(["add", *paths], cwd=path)

        if action is ActionType.COMMIT:
            return _run(["commit", "-m", params["message"]], cwd=path)

        if action is ActionType.PUSH:
            remote = params.get("remote") or "origin"
            branch = params.get("branch") or current_branch(path)
            args = ["push", remote, branch]
            if params.get("force"):
                args.append("--force")
            return _run(args, cwd=path, access_token=access_token, needs_auth=True)

        if action is ActionType.PULL:
            remote = params.get("remote") or "origin"
            branch = params.get("branch") or current_branch(path)
            return _run(["pull", remote, branch], cwd=path, access_token=access_token, needs_auth=True)

        if action is ActionType.BRANCH:
            return _run(["branch", params["name"]], cwd=path)

        if action is ActionType.CHECKOUT:
            return _run(["checkout", params["ref"]], cwd=path)

        if action is ActionType.MERGE:
            return _run(["merge", params["ref"]], cwd=path)

        if action is ActionType.RESET:
            return _run(["reset", f"--{params['mode']}", params["target"]], cwd=path)

        if action is ActionType.STASH:
            return _run(["stash"], cwd=path)

        if action is ActionType.LOG:
            limit = str(params.get("limit") or 20)
            return _run(["log", f"-n{limit}", "--oneline"], cwd=path)

        if action is ActionType.DIFF:
            return _run(["diff"], cwd=path)

        raise LocalGitError(f"No local execution handler for '{action.value}'")


def reset_soft(path: Path, sha: str) -> str:
    """Used by history/service.py to undo a commit -- resets to exactly the
    sha recorded as this action's pre_state, not an assumed "HEAD~1".
    """
    return _run(["reset", "--soft", sha], cwd=path)


def delete_branch(path: Path, name: str) -> str:
    """Used by history/service.py to undo a branch creation."""
    return _run(["branch", "-d", name], cwd=path)
