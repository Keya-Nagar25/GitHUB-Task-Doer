import type {
  ActionLogSummary,
  CommitSummary,
  ExecuteResponse,
  ResolveResponse,
  ResolvedAction,
  RepoRef,
} from "../types";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

async function request<T>(
  path: string,
  options: RequestInit & { sessionToken?: string | null } = {},
): Promise<T> {
  const { sessionToken, headers, ...rest } = options;
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...rest,
    headers: {
      "Content-Type": "application/json",
      ...(sessionToken ? { Authorization: `Bearer ${sessionToken}` } : {}),
      ...headers,
    },
  });

  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new ApiError(response.status, body.detail ?? `Request failed (${response.status})`);
  }
  return response.json() as Promise<T>;
}

export function resolveText(text: string): Promise<ResolveResponse> {
  return request<ResolveResponse>("/resolve", {
    method: "POST",
    body: JSON.stringify({ text }),
  });
}

export function executeAction(
  resolvedAction: ResolvedAction,
  repo: RepoRef,
  sessionToken: string,
): Promise<ExecuteResponse> {
  return request<ExecuteResponse>("/execute", {
    method: "POST",
    sessionToken,
    body: JSON.stringify({ resolved_action: resolvedAction, repo, confirmed: true }),
  });
}

export function undoAction(actionLogId: string, sessionToken: string): Promise<{ status: string; result: unknown }> {
  return request(`/undo/${actionLogId}`, { method: "POST", sessionToken });
}

export function getLoginUrl(): Promise<{ authorize_url: string }> {
  return request("/auth/github/login");
}

export function getRepoHistory(repo: RepoRef, sessionToken: string, limit = 20): Promise<CommitSummary[]> {
  return request(`/repo/${repo.owner}/${repo.repo}/history?limit=${limit}`, { sessionToken });
}

export function getActionHistory(sessionToken: string): Promise<ActionLogSummary[]> {
  return request("/history/actions", { sessionToken });
}
