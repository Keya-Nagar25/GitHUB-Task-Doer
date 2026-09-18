# GitHub Task Doer -- Web

React + Vite + TypeScript front end for the assistant.

## Dev setup

```bash
npm install
cp .env.example .env.local   # point VITE_API_BASE_URL at your backend if not localhost:8000
npm run dev
```

The backend (`../backend`) must be running for anything beyond the empty page to work.

## How it maps to the architecture

- `src/api/client.ts` -- typed fetch wrapper for `/resolve`, `/execute`, `/undo`, `/repo/.../history`, `/history/actions`, `/auth/github/login`.
- `src/components/ChatInput.tsx` / `ConfirmPanel.tsx` -- the explain -> confirm -> execute flow. "Confirm & Run" executes every action for real once you're logged in and a repo is selected: GitHub REST actions (create PR/issue/fork) call the GitHub API directly, everything else runs as a real git command against a server-side clone of the repo (see `../docs/architecture.md`, Execution locality). "Copy command" is always available too.
- `src/components/HistoryTimeline.tsx` -- the assistant's own undo-able action log, plus read-only commit history browsing.
- Session token comes back from the backend's OAuth callback as a URL fragment (`#session_token=...`) and is kept in `sessionStorage`; the selected repo is kept in `localStorage` as a convenience. Neither is synced anywhere else.
