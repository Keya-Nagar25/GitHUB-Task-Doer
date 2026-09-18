# GitHub Task Doer

A GitHub command assistant that lets Git/GitHub beginners use plain English instead of memorizing commands. Type "undo my last commit" and get the exact command, a plain-English explanation of its effect, and a confirm step before anything runs.

## How it works

- **Explain -> Confirm -> Execute.** Every request resolves to an exact command plus an explanation. Nothing runs until you click Confirm & Run.
- **Hybrid understanding.** An offline local classifier (`sentence-transformers`) handles common phrasing with no network required; the Claude API handles more open-ended requests when you're online.
- **Undo & time travel.** Actions are logged so most can be undone, and you can safely browse or roll back to a previous version of your project.

## Project layout

- `backend/` - Python/FastAPI service: intent resolution (offline + online), validation, GitHub API execution, undo/history log.
- `web/` - Web app front end.
- `vscode-extension/` - VS Code extension for executing local git operations on your machine.
- `intent-data/` - Shared catalog of supported actions, used by both the offline classifier and the online LLM contract.
- `docs/architecture.md` - Full architecture and build plan.

## Status

Early scaffolding. See `docs/architecture.md` for the current design and milestone plan.

## Backend dev setup

```bash
cd backend
pip install -e ".[dev]"
uvicorn app.main:app --reload
```
