import type { ResolvedAction } from "./types";

// Renders the literal command a ResolvedAction corresponds to, for display
// and copy/paste only -- this is never executed by the web app itself. Local
// working-tree actions execute for real only via the VS Code extension; see
// docs/architecture.md, Execution model.
export function commandPreview(action: ResolvedAction): string {
  const p = action.params as Record<string, string | undefined>;

  switch (action.action) {
    case "add":
      return "git add .";
    case "commit":
      return `git commit -m "${p.message ?? ""}"`;
    case "push":
      return `git push ${p.remote ?? "origin"}${p.branch ? ` ${p.branch}` : ""}${p.force === "true" ? " --force" : ""}`;
    case "pull":
      return `git pull ${p.remote ?? "origin"}${p.branch ? ` ${p.branch}` : ""}`;
    case "branch":
      return `git branch ${p.name ?? ""}`;
    case "checkout":
      return `git checkout ${p.ref ?? ""}`;
    case "merge":
      return `git merge ${p.ref ?? ""}`;
    case "reset":
      return `git reset --${p.mode ?? "soft"} ${p.target ?? "HEAD~1"}`;
    case "stash":
      return "git stash";
    case "log":
      return `git log -n ${p.limit ?? 20}`;
    case "diff":
      return "git diff";
    case "github_create_pr":
      return `gh pr create --title "${p.title ?? ""}" --head ${p.head ?? ""} --base ${p.base ?? "main"}`;
    case "github_open_issue":
      return `gh issue create --title "${p.title ?? ""}"${p.body ? ` --body "${p.body}"` : ""}`;
    case "github_fork":
      return `gh repo fork ${p.owner && p.repo ? `${p.owner}/${p.repo}` : "(this repo)"}`;
    default:
      return "";
  }
}
