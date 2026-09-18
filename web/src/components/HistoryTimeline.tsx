import { useEffect, useState } from "react";
import { getActionHistory, getRepoHistory, undoAction } from "../api/client";
import type { ActionLogSummary, CommitSummary, RepoRef } from "../types";

interface HistoryTimelineProps {
  repo: RepoRef;
  sessionToken: string;
  refreshTrigger: number;
}

export function HistoryTimeline({ repo, sessionToken, refreshTrigger }: HistoryTimelineProps) {
  const [commits, setCommits] = useState<CommitSummary[]>([]);
  const [actions, setActions] = useState<ActionLogSummary[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [undoingId, setUndoingId] = useState<string | null>(null);

  const loadActions = () => {
    getActionHistory(sessionToken)
      .then(setActions)
      .catch((err) => setError(err.message));
  };

  useEffect(() => {
    setError(null);
    loadActions();
    if (repo.owner && repo.repo) {
      getRepoHistory(repo, sessionToken)
        .then(setCommits)
        .catch((err) => setError(err.message));
    } else {
      setCommits([]);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [repo.owner, repo.repo, sessionToken, refreshTrigger]);

  const handleUndo = async (entry: ActionLogSummary) => {
    setUndoingId(entry.id);
    setError(null);
    try {
      await undoAction(entry.id, sessionToken);
      loadActions();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Undo failed");
    } finally {
      setUndoingId(null);
    }
  };

  return (
    <aside className="history-timeline">
      {error && <p className="history-timeline__error">{error}</p>}

      <h3>Recent actions</h3>
      {actions.length === 0 ? (
        <p className="history-timeline__empty">Nothing executed yet.</p>
      ) : (
        <ul className="history-timeline__actions">
          {actions.map((entry) => (
            <li key={entry.id}>
              <span className={entry.undone ? "history-timeline__undone" : ""}>
                {entry.action} on {entry.repo_owner}/{entry.repo_name}
              </span>
              {!entry.undone && entry.undo_strategy === "api_delete" && (
                <button disabled={undoingId === entry.id} onClick={() => handleUndo(entry)}>
                  {undoingId === entry.id ? "Undoing..." : "Undo"}
                </button>
              )}
            </li>
          ))}
        </ul>
      )}

      {repo.owner && repo.repo && (
        <>
          <h3>
            Commit history -- {repo.owner}/{repo.repo}
          </h3>
          {commits.length === 0 ? (
            <p className="history-timeline__empty">No commits loaded yet.</p>
          ) : (
            <ul className="history-timeline__commits">
              {commits.map((c) => (
                <li key={c.sha}>
                  <a href={c.html_url} target="_blank" rel="noreferrer">
                    {c.sha.slice(0, 7)}
                  </a>{" "}
                  {c.message.split("\n")[0]}
                </li>
              ))}
            </ul>
          )}
        </>
      )}
    </aside>
  );
}
