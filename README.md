# GitHub Task Doer

A GitHub command assistant that lets Git/GitHub beginners use plain English instead of memorizing commands. Type "undo my last commit" and get the exact command, a plain-English explanation of its effect, and a confirm step before anything runs.

## How it works

- **Explain -> Confirm -> Execute.** Every request resolves to an exact command plus an explanation. Nothing runs until you click Confirm & Run.
- **Hybrid understanding.** An offline local classifier (`sentence-transformers`) handles common phrasing with no network required; the Claude API handles more open-ended requests when you're online.
- **Undo & time travel.** Actions are logged so most can be undone, and you can safely browse or roll back to a previous version of your project.

## Project layout

- `backend/` - Python/FastAPI service: intent resolution (offline + online), validation, GitHub API execution, server-side git execution (clones repos per-user to run git commands for real), undo/history log.
- `web/` - Web app front end. Executes every action for real once you're logged in with GitHub and have picked a repo.
- `vscode-extension/` - Planned: will act on your actual local working copy, including uncommitted changes (not yet built).
- `intent-data/` - Shared catalog of supported actions, used by both the offline classifier and the online LLM contract.
- `docs/architecture.md` - Full architecture and build plan.

## Status

Intent resolution, GitHub OAuth, and execution (GitHub REST actions + real server-side git execution) are working end-to-end, with an undo/history log and a web frontend. GitHub OAuth App credentials aren't registered yet, so login/execution can't be exercised live until that's set up. See `docs/architecture.md` for the current design and milestone plan.

## Backend dev setup

```bash
cd backend
pip install -e ".[dev]"
uvicorn app.main:app --reload
```

Set `ANTHROPIC_API_KEY` to enable the online (Claude API) fallback for phrasing the offline classifier doesn't confidently recognize. Without it, `/resolve` still works fully offline -- it just won't have the online fallback for ambiguous or unusual phrasing.

Try it without a server: `python scripts/cli_demo.py`.
