import { useEffect, useState } from "react";
import "./App.css";
import { ChatInput } from "./components/ChatInput";
import { ConfirmPanel } from "./components/ConfirmPanel";
import { HistoryTimeline } from "./components/HistoryTimeline";
import { RepoSelector } from "./components/RepoSelector";
import { executeAction, getLoginUrl, resolveText } from "./api/client";
import { GITHUB_API_ACTIONS, type ResolvedAction, type RepoRef } from "./types";

interface Turn {
  id: string;
  text: string;
  status: "resolved" | "needs_clarification" | "unresolved" | "error";
  resolvedAction: ResolvedAction | null;
  message: string | null;
  executing: boolean;
  executed: boolean;
  executeResult: string | null;
}

function readStoredSession(): { token: string; login: string } | null {
  try {
    const token = sessionStorage.getItem("session_token");
    const login = sessionStorage.getItem("github_login");
    return token && login ? { token, login } : null;
  } catch {
    return null;
  }
}

function readStoredRepo(): RepoRef {
  try {
    const raw = localStorage.getItem("last_repo");
    if (raw) return JSON.parse(raw) as RepoRef;
  } catch {
    // ignore -- localStorage can throw or be unavailable
  }
  return { owner: "", repo: "" };
}

function App() {
  const [session, setSession] = useState<{ token: string; login: string } | null>(readStoredSession);
  const [repo, setRepo] = useState<RepoRef>(readStoredRepo);
  const [turns, setTurns] = useState<Turn[]>([]);
  const [asking, setAsking] = useState(false);
  const [historyRefreshTrigger, setHistoryRefreshTrigger] = useState(0);

  // Pick up the session token GitHub OAuth callback redirected back with.
  useEffect(() => {
    const hash = new URLSearchParams(window.location.hash.replace(/^#/, ""));
    const token = hash.get("session_token");
    const params = new URLSearchParams(window.location.search);
    const login = params.get("github_login");
    if (token && login) {
      try {
        sessionStorage.setItem("session_token", token);
        sessionStorage.setItem("github_login", login);
      } catch {
        // best-effort persistence; the in-memory state below still works for this page load
      }
      setSession({ token, login });
      window.history.replaceState({}, "", window.location.pathname);
    }
  }, []);

  useEffect(() => {
    try {
      localStorage.setItem("last_repo", JSON.stringify(repo));
    } catch {
      // per-viewer convenience only -- fine if this silently no-ops
    }
  }, [repo]);

  const handleLogin = async () => {
    try {
      const { authorize_url } = await getLoginUrl();
      window.location.href = authorize_url;
    } catch (err) {
      alert(err instanceof Error ? err.message : "Could not start GitHub login");
    }
  };

  const handleLogout = () => {
    try {
      sessionStorage.removeItem("session_token");
      sessionStorage.removeItem("github_login");
    } catch {
      // ignore
    }
    setSession(null);
  };

  const handleAsk = async (text: string) => {
    setAsking(true);
    const id = crypto.randomUUID();
    try {
      const response = await resolveText(text);
      setTurns((prev) => [
        ...prev,
        {
          id,
          text,
          status: response.status,
          resolvedAction: response.resolved_action,
          message: response.message,
          executing: false,
          executed: false,
          executeResult: null,
        },
      ]);
    } catch (err) {
      setTurns((prev) => [
        ...prev,
        {
          id,
          text,
          status: "error",
          resolvedAction: null,
          message: err instanceof Error ? err.message : "Something went wrong",
          executing: false,
          executed: false,
          executeResult: null,
        },
      ]);
    } finally {
      setAsking(false);
    }
  };

  const handleConfirm = async (turnId: string) => {
    const turn = turns.find((t) => t.id === turnId);
    if (!turn?.resolvedAction) return;

    if (!GITHUB_API_ACTIONS.has(turn.resolvedAction.action)) return;

    if (!session) {
      setTurns((prev) =>
        prev.map((t) => (t.id === turnId ? { ...t, message: "Log in with GitHub first to run this." } : t)),
      );
      return;
    }

    if (!repo.owner || !repo.repo) {
      setTurns((prev) =>
        prev.map((t) => (t.id === turnId ? { ...t, message: "Pick a repo (top right) first." } : t)),
      );
      return;
    }

    setTurns((prev) => prev.map((t) => (t.id === turnId ? { ...t, executing: true } : t)));
    try {
      const response = await executeAction(turn.resolvedAction, repo, session.token);
      const url = typeof response.result.html_url === "string" ? response.result.html_url : null;
      setTurns((prev) =>
        prev.map((t) =>
          t.id === turnId
            ? { ...t, executing: false, executed: true, executeResult: url ?? "Done" }
            : t,
        ),
      );
      setHistoryRefreshTrigger((n) => n + 1);
    } catch (err) {
      setTurns((prev) =>
        prev.map((t) =>
          t.id === turnId
            ? { ...t, executing: false, message: err instanceof Error ? err.message : "Execution failed" }
            : t,
        ),
      );
    }
  };

  return (
    <div className="app">
      <header className="app__header">
        <h1>GitHub Task Doer</h1>
        <div className="app__header-right">
          <RepoSelector repo={repo} onChange={setRepo} />
          {session ? (
            <span className="app__session">
              {session.login} <button onClick={handleLogout}>Log out</button>
            </span>
          ) : (
            <button onClick={handleLogin}>Log in with GitHub</button>
          )}
        </div>
      </header>

      <div className="app__body">
        <main className="app__conversation">
          {turns.length === 0 && (
            <p className="app__empty">
              Describe what you want to do with Git or GitHub in plain English. You'll always see the
              exact command and an explanation before anything runs.
            </p>
          )}

          {turns.map((turn) => (
            <div key={turn.id} className="turn">
              <p className="turn__prompt">{turn.text}</p>

              {turn.status === "resolved" && turn.resolvedAction && (
                <>
                  <ConfirmPanel
                    resolvedAction={turn.resolvedAction}
                    executing={turn.executing}
                    executed={turn.executed}
                    onConfirm={() => handleConfirm(turn.id)}
                  />
                  {turn.message && <p className="turn__note">{turn.message}</p>}
                  {turn.executeResult && (
                    <p className="turn__result">
                      Done --{" "}
                      {turn.executeResult.startsWith("http") ? (
                        <a href={turn.executeResult} target="_blank" rel="noreferrer">
                          view on GitHub
                        </a>
                      ) : (
                        turn.executeResult
                      )}
                    </p>
                  )}
                </>
              )}

              {(turn.status === "needs_clarification" ||
                turn.status === "unresolved" ||
                turn.status === "error") && <p className="turn__note">{turn.message}</p>}
            </div>
          ))}

          <ChatInput onSubmit={handleAsk} disabled={asking} />
        </main>

        {session && <HistoryTimeline repo={repo} sessionToken={session.token} refreshTrigger={historyRefreshTrigger} />}
      </div>
    </div>
  );
}

export default App;
