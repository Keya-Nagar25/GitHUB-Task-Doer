import re
from enum import Enum
from typing import Annotated, Literal

from pydantic import AfterValidator, BaseModel, Field

# A safe git ref: letters, digits, and - _ . / only, no leading '-', no '..'.
# This is the primary defense against shell/argument injection via ref-like params.
# Pydantic's `pattern=` compiles with Rust's `regex` crate, which has no
# look-around support, so the leading-'-'/'..' checks are done in Python here.
_GIT_REF_CHARSET_RE = re.compile(r"^[A-Za-z0-9_\-./~^]{1,255}$")


def _validate_git_ref(value: str) -> str:
    if not _GIT_REF_CHARSET_RE.match(value):
        raise ValueError("must contain only letters, digits, '-', '_', '.', '/'")
    if value.startswith("-"):
        raise ValueError("must not start with '-'")
    if ".." in value:
        raise ValueError("must not contain '..'")
    return value


GitRef = Annotated[str, AfterValidator(_validate_git_ref)]


class ActionType(str, Enum):
    ADD = "add"
    COMMIT = "commit"
    PUSH = "push"
    PULL = "pull"
    BRANCH = "branch"
    CHECKOUT = "checkout"
    MERGE = "merge"
    RESET = "reset"
    STASH = "stash"
    LOG = "log"
    DIFF = "diff"
    GITHUB_CREATE_PR = "github_create_pr"
    GITHUB_OPEN_ISSUE = "github_open_issue"
    GITHUB_FORK = "github_fork"


class AddParams(BaseModel):
    paths: list[str] = Field(default_factory=lambda: ["."])


class CommitParams(BaseModel):
    message: str = Field(min_length=1, max_length=2000)


class PushParams(BaseModel):
    remote: GitRef = "origin"
    branch: GitRef | None = None
    force: bool = False


class PullParams(BaseModel):
    remote: GitRef = "origin"
    branch: GitRef | None = None


class BranchParams(BaseModel):
    name: GitRef


class CheckoutParams(BaseModel):
    ref: GitRef


class MergeParams(BaseModel):
    ref: GitRef


class ResetParams(BaseModel):
    mode: Literal["soft", "hard"]
    target: GitRef


class StashParams(BaseModel):
    pass


class LogParams(BaseModel):
    limit: int = Field(default=20, ge=1, le=200)


class DiffParams(BaseModel):
    pass


class GithubCreatePRParams(BaseModel):
    title: str = Field(min_length=1, max_length=256)
    head: GitRef
    base: GitRef = "main"


class GithubOpenIssueParams(BaseModel):
    title: str = Field(min_length=1, max_length=256)
    body: str = Field(default="", max_length=10000)


class GithubForkParams(BaseModel):
    owner: GitRef
    repo: GitRef


# One param model per action; the validator uses this as its whitelist.
ACTION_PARAM_MODELS: dict[ActionType, type[BaseModel]] = {
    ActionType.ADD: AddParams,
    ActionType.COMMIT: CommitParams,
    ActionType.PUSH: PushParams,
    ActionType.PULL: PullParams,
    ActionType.BRANCH: BranchParams,
    ActionType.CHECKOUT: CheckoutParams,
    ActionType.MERGE: MergeParams,
    ActionType.RESET: ResetParams,
    ActionType.STASH: StashParams,
    ActionType.LOG: LogParams,
    ActionType.DIFF: DiffParams,
    ActionType.GITHUB_CREATE_PR: GithubCreatePRParams,
    ActionType.GITHUB_OPEN_ISSUE: GithubOpenIssueParams,
    ActionType.GITHUB_FORK: GithubForkParams,
}


class ResolvedAction(BaseModel):
    action: ActionType
    params: dict
    explanation: str
    destructive: bool
    requires_double_confirmation: bool = False
    confidence: Literal["low", "medium", "high"]
    matched_intent_id: str | None = None
    clarifying_question: str | None = None
    source: Literal["offline", "online"]
