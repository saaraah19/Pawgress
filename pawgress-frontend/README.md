# Pawgress Frontend — Slice 1, Piece 1 (Auth only)

Scope of this piece: project scaffold, typed API client, Register/Login, and a
placeholder authenticated screen that proves the token round-trips. No
capture UI, no task list yet — that's the next piece.

## Setup

1. Make sure your backend is running locally (uvicorn, per its own README) —
   default expected at `http://localhost:8000`.
2. In this folder:
   ```
   npm install
   copy .env.example .env
   ```
   (On Windows, `copy` is the built-in equivalent of `cp`. Edit `.env` only
   if your backend isn't on `localhost:8000`.)
3. Start the dev server:
   ```
   npm run dev
   ```
4. Open the URL Vite prints (default `http://localhost:5173`).

## What to test

1. **Register** — go to `/register`, create an account with a real-looking
   email and an 8+ character password. On success you should land on `/`
   and see "You're logged in" with your user ID shown.
2. **Duplicate email** — try registering the same email again. You should
   see the backend's actual message ("An account with this email already
   exists...") — not a generic error, and not a scary red banner.
3. **Log out, then log back in** — click "Log out," you should land on
   `/login`. Log back in with the same credentials — should land on `/`
   again.
4. **Wrong password** — try logging in with the wrong password. You should
   see "Incorrect email or password." with the same calm styling, no red.
5. **Session persistence** — while logged in, refresh the page (F5). You
   should stay on `/` without being bounced to `/login` (FR-1.2). Then
   close the tab entirely, reopen `http://localhost:5173` — should still be
   logged in (token is in `localStorage`, 7-day expiry set server-side).
6. **Route guard** — while logged out, try navigating directly to
   `http://localhost:5173/` — should redirect to `/login`, not show a
   broken page.

## What's deliberately not here yet

- No capture input, no extracted-task display, no task list, no correction
  UI. Next piece.
- No cat companion — out of scope for this slice per your instruction.
- No password-reset / email-verification flow — not in the Functional
  Requirements for MVP auth (FR-1.1–1.3 only cover creation + session
  persistence).

## Known gap carried forward from the backend contract

FR-2.7 requires a manual-fallback path when extraction fails ("retry or
manually create a task from it"). The current backend contract has no
`POST /tasks` for manual creation, so the failure-state UI (next piece)
will only be able to offer **retry**, not manual entry. Flagged, not
silently resolved — see the conversation where this was raised.
