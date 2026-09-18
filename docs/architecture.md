# GitHub Task Doer — v1 Architecture & Build Plan

## Context

This is a new, empty project (`C:\Users\Keya Nagar\OneDrive\Desktop\GitHub Task Doer`, pushed to `https://github.com/Keya-Nagar25/GitHub-TaskDoer.git`) — no existing code at the time this was written. The goal: a "GitHub command assistant" that lets Git/GitHub beginners type plain English (e.g. "undo my last commit") instead of memorizing commands, and get back the exact command plus a plain-English explanation of its effect.

Confirmed direction, through several rounds of clarification:
- Two front-ends sharing one Python backend: a **web app** (primary) and a **VS Code extension** (downloadable from the web app, TypeScript by platform necessity).
- **Hybrid NLU**: online Claude API for open-ended phrasing (GenAI) + an offline local embedding classifier for no-network use (classical ML) — this is intentional, so the project has real ML *and* GenAI substance, not just an API wrapper.
- **Explain → Confirm → Execute**: every action is shown with its exact command + explanation, and only runs after an explicit "Confirm & Run" click — no silent execution.
- **v1 scope**: core git (clone/add/commit/push/pull/branch/merge/checkout/reset/stash/log/diff/.gitignore) + GitHub REST actions (create PR, open issue, fork), plus an **undo/action-history log** and a **time-travel/rollback** feature (browse old versions safely vs. actually rolling back, treated as distinct, differently-guarded actions).
- **Execution locality** (the key safety decision, explicitly confirmed with the user): the web app executes directly only what's expressible via the GitHub REST API (PRs, issues, forks, single-file edits via the Contents API). Anything needing a real local working tree (commit, push, branch, checkout, etc.) executes for real only through the **VS Code extension**, running locally on the user's machine; without the extension, the web app still shows the exact command to copy/run manually. This avoids a hosted backend ever running arbitrary shell git commands server-side.

## Architecture

```
Web Frontend (React/Vite+TS)          VS Code Extension (TypeScript)
  - chat input, confirm panel           - webview chat input, confirm panel
  - GitHub-API actions execute            - LOCAL execution via execFile,
    server-side on confirm                  against the open workspace
  - local-tree actions: show command      - talks to backend for NLU only
    to copy if extension not installed
        │ HTTPS/JSON (resolve, execute-via-API)   │ HTTPS/JSON (resolve only)
        ▼                                          ▼
┌───────────────────────────────────────────────────────────────────┐
│                 Backend API (FastAPI, Python)                      │
│  nlu/router.py --> offline_classifier.py (sentence-transformers)   │
│                 --> online_llm.py (Claude API, tool-calling)       │
│  actions/validator.py  -- single choke point, whitelist + Pydantic │
│  actions/github_client.py -- only thing that executes (GitHub API) │
│  history/service.py -- action log + undo-strategy dispatch         │
└───────────────────────────────────────────────────────────────────┘
```

The backend **never** shells out to `git` against arbitrary user-specified paths. It only (a) resolves English → a validated structured action, and (b) executes GitHub-REST-shaped actions on behalf of an OAuth-authorized user. Real local `git` execution happens exclusively inside the VS Code extension, on the user's own machine, via `child_process.execFile` (never a raw shell string — avoids injection).

## Core building blocks

**Shared action taxonomy** (`intent-data/intents.yaml`): single source of truth for both the offline classifier and the LLM's tool-calling contract. Each entry has `intent_id`, `action`, `param_schema`, `example_phrases`, `destructive: bool`, `undo_strategy`. Starts with ~10 core intents (commit, add, push, pull, branch, checkout, reset-soft-undo-commit, log, diff, stash) and grows from there.

**Offline NLU** (`backend/app/nlu/offline_classifier.py`): `sentence-transformers` (`all-MiniLM-L6-v2`, CPU-friendly) embeds `example_phrases` from `intents.yaml` (cached, rebuilt on content-hash change). Cosine similarity against user input: ≥0.75 resolve directly, 0.55–0.75 resolve but surface as "did you mean X?" in the confirm screen, <0.55 return "couldn't confidently match, try rephrasing or go online" — never guesses. Pure function, no network, unit-testable — first real milestone.

**Online NLU** (`backend/app/nlu/online_llm.py`): Claude API tool-calling, constrained to a `resolve_git_action` tool whose schema mirrors the same intent taxonomy (whitelisted `action` enum, `params`, `explanation`, `destructive`, `confidence`, optional `clarifying_question` instead of guessing).

**Validator** (`backend/app/actions/validator.py`): the one choke point every resolution (offline or online) passes through before reaching execution or even being shown to the user. Re-checks `action` against a server-side Python `Enum` (never trusts the LLM string), validates `params` per-action via strict Pydantic models (e.g. `ref` regex-constrained to valid git-ref characters), and sets `requires_double_confirmation: true` for `reset --hard` / force-push style actions.

**Undo / history log** (`backend/app/history/service.py`, `ActionLogEntry` model): separate from git's own reflog. Stores `pre_state`/`post_state` (e.g. HEAD sha) captured around each execution, so undo replays a computed action against the recorded state rather than assuming "the last thing." Per-action `undo_strategy` (`reset_soft`, `revert`, `api_delete`, `manual_only`, `not_undoable`) — `push` and `reset --hard` are intentionally **not** one-click-undoable (guidance only), since automating undo of shared/destroyed history risks double damage.

**Time-travel/rollback**: two distinct, separately-labeled affordances — "View this version" (safe, detached-HEAD browsing with a persistent "return to latest" banner) vs. "Roll back to this version" (destructive; recommends `git revert`/new-branch-plus-PR by default, with `reset --hard` as a second, separately-worded, type-the-sha-to-confirm option).

**GitHub REST integration**: OAuth App flow (not raw PATs) for the web app; VS Code's built-in `vscode.authentication.getSession('github', scopes)` for the extension. Scopes: `repo`, `read:user`. Endpoints: create PR, open issue, fork, plus their close/delete counterparts for undo, plus commits list for history browsing.

## Repo layout

```
GitHub-TaskDoer/
├── backend/app/{api,nlu,actions,history}/...   # FastAPI service
├── web/src/...                                  # React/Vite + TS
├── vscode-extension/src/...                     # TypeScript
├── intent-data/intents.yaml                     # shared source of truth
├── docs/architecture.md                         # this plan, checked in
└── .github/workflows/                           # CI
```

## Build order (milestones)

1. **Scaffolding**: monorepo layout, `backend/pyproject.toml` (fastapi, uvicorn, pydantic, sentence-transformers, httpx, sqlmodel), `intent-data/intents.yaml` seeded with ~10 core intents, git init, first push to the GitHub-TaskDoer remote.
2. **Offline NLU + `/resolve`, CLI-first**: `offline_classifier.py`, `actions/schema.py`, `actions/validator.py`, `api/resolve.py`, plus a throwaway terminal demo script to validate matching before any UI exists.
3. **Online LLM path + router**: `nlu/online_llm.py`, `nlu/router.py` (offline-first, online fallback for low-confidence/no-match).
4. **GitHub OAuth + execution + undo log**: `api/auth.py`, `actions/github_client.py`, `api/execute.py`, `history/models.py`, `history/service.py`, `api/undo.py`. First true end-to-end slice: resolve → confirm → real GitHub API execution → logged → undoable.
5. **Web frontend**: chat input, confirm panel, GitHub login, history timeline for time-travel browsing.
6. **VS Code extension**: webview chat panel reusing `/resolve`, local execution via `execFile`, VS Code's GitHub auth provider, local history store synced to backend.
7. **Polish**: double-confirmation for destructive resets, remaining undo-strategy coverage (merge, stash), packaging (web deploy + VS Code Marketplace listing).

## Verification

- Milestone 2: run the CLI demo script with representative phrases for each seeded intent and confirm correct resolution + confidence banding; add unit tests for the classifier's threshold behavior.
- Milestone 3: unit tests asserting the validator rejects out-of-whitelist actions and malformed params (e.g. shell-metacharacter-laden `ref` values).
- Milestone 4: manual end-to-end test — authenticate, resolve "open an issue saying X" against a real (test) repo, confirm, verify it's created on GitHub, verify it appears in the action log, then undo it and verify the issue is closed.
- Milestone 5/6: manual test in an actual VS Code window against a scratch local repo — resolve a commit/branch/checkout phrase, confirm, verify the real local repo state changes as expected, and test the "view this version" vs "roll back" flows for accidental-data-loss guarding.

## Flagged deviations / judgment calls

- VS Code extension is TypeScript, not Python — unavoidable platform constraint.
- Web app cannot directly execute local working-tree git ops (confirmed with user): those require the VS Code extension, or fall back to copy/paste of the shown command.
- `push` and `reset --hard` are undo-guidance-only, not one-click undoable, to avoid compounding destructive actions.
