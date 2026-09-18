import type { RepoRef } from "../types";

interface RepoSelectorProps {
  repo: RepoRef;
  onChange: (repo: RepoRef) => void;
}

export function RepoSelector({ repo, onChange }: RepoSelectorProps) {
  return (
    <div className="repo-selector">
      <span className="repo-selector__label">Repo:</span>
      <input
        type="text"
        value={repo.owner}
        placeholder="owner"
        onChange={(e) => onChange({ ...repo, owner: e.target.value.trim() })}
      />
      <span className="repo-selector__slash">/</span>
      <input
        type="text"
        value={repo.repo}
        placeholder="repo"
        onChange={(e) => onChange({ ...repo, repo: e.target.value.trim() })}
      />
    </div>
  );
}
