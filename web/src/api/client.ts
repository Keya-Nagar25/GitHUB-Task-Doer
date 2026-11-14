import type {
  ActionLogSummary,
  CommitSummary,
  ExecuteResponse,
  ResolveResponse,
  ResolvedAction,
  RepoRef,
} from "../types";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

export const SESSION_EXPIRED_EVENT = "taskdoer:session-expired";

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
  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      ...rest,
      headers: {
        "Content-Type": "application/json",
        ...(sessionToken ? { Authorization: `Bearer ${sessionToken}` } : {}),
        ...headers,
      },
    });
  } catch {
    // fetch only throws when no response came back at all (server down, wrong URL, CORS).
    throw new ApiError(0, `Can't reach the backend at ${API_BASE_URL}. Is it running? (cd backend, then: uvicorn app.main:app --reload)`);
  }

  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    if (response.status === 401 && sessionToken) {
      // The backend no longer recognises this login -- let App log out.
      window.dispatchEvent(new Event(SESSION_EXPIRED_EVENT));
    }
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
