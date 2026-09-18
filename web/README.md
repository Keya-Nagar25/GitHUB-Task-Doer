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
- `src/components/ChatInput.tsx` / `ConfirmPanel.tsx` -- the explain -> confirm -> execute flow. `ConfirmPanel` only offers a real "Confirm & Run" for GitHub-API-shaped actions (create PR/issue/fork); anything needing a local working copy shows the exact command to copy instead, per the execution-locality design in `../docs/architecture.md`.
- `src/components/HistoryTimeline.tsx` -- the assistant's own undo-able action log, plus read-only commit history browsing.
- Session token comes back from the backend's OAuth callback as a URL fragment (`#session_token=...`) and is kept in `sessionStorage`; the selected repo is kept in `localStorage` as a convenience. Neither is synced anywhere else.
