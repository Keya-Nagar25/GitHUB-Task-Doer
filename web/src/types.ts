// Mirrors backend/app/actions/schema.py -- keep these in sync by hand for now
// (small enough surface that a generated client isn't worth it yet).

export type ActionType =
  | "add"
  | "commit"
  | "push"
  | "pull"
  | "branch"
  | "checkout"
  | "merge"
  | "reset"
  | "stash"
  | "log"
  | "diff"
  | "github_create_pr"
  | "github_open_issue"
  | "github_fork";

export interface ResolvedAction {
  action: ActionType;
  params: Record<string, unknown>;
  explanation: string;
  destructive: boolean;
  requires_double_confirmation: boolean;
  confidence: "low" | "medium" | "high";
  matched_intent_id: string | null;
  clarifying_question: string | null;
  source: "offline" | "online";
}

export interface ResolveResponse {
  status: "resolved" | "needs_clarification" | "unresolved";
  resolved_action: ResolvedAction | null;
  message: string | null;
}

export interface RepoRef {
  owner: string;
  repo: string;
}

export interface ExecuteResponse {
  status: string;
  result: Record<string, unknown>;
  action_log_id: string;
}

export interface CommitSummary {
  sha: string;
  message: string;
  author: string | null;
  date: string | null;
  html_url: string;
}

export interface ActionLogSummary {
  id: string;
  action: string;
  repo_owner: string;
  repo_name: string;
  undo_strategy: string;
  undone: boolean;
  created_at: string;
}
