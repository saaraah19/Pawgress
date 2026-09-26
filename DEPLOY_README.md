# Single-service deployment on Render (2026-09-16)

## Files to add/overwrite
- `build.sh` — **new, at repo root** (sibling to `pawgress-backend/` and
  `pawgress-frontend/`).
- `pawgress-backend/main.py` — now serves the built frontend as static
  files, with an SPA fallback route registered after every API router.
- `pawgress-backend/.gitignore` — added `static/` (the build output
  `build.sh` copies in — never commit it, it's generated).

## What changed and why
`main.py`'s new bottom section only activates if `pawgress-backend/static/`
exists — absent in local dev (Vite's dev server still handles the
frontend there), present after a real build. The catch-all route is
registered **last**, after every API router — FastAPI matches routes in
registration order, so a real API path is always resolved by its own
router first; the catch-all only ever sees paths no API router claimed,
which in practice means your frontend's own client-side routes
(`/planner`, `/goals`, etc.) when someone loads them directly instead of
navigating there from inside the app.

## Render dashboard settings

**Service type**: Web Service (not Static Site — the backend needs to run
as a real process).

**Environment**: Python 3.

**Build command**:
```
bash build.sh
```

**Start command**:
```
cd pawgress-backend && alembic upgrade head && uvicorn main:app --host 0.0.0.0 --port $PORT
```
Running the migration as part of the start command is a pragmatic
solo-project choice — it re-runs on every deploy, which is harmless
(Alembic no-ops if there's nothing new to apply) but means a bad
migration could block startup. If Render's plan you're on supports a
separate **pre-deploy command**, move `cd pawgress-backend && alembic
upgrade head` there instead and keep the start command to just the
`uvicorn` line — cleaner separation, worth doing once you've confirmed
the basic setup works.

**One real unknown, worth checking in the build logs the first time**:
whether Render's native Python environment image includes Node.js/npm
(needed for `build.sh`'s frontend build step). Many people run this exact
pattern successfully on Render's Python image, but I can't verify it
from my sandbox. If the build log shows `npm: command not found`, the
fix is either switching to Render's Docker environment with a Dockerfile
that installs both Python and Node, or adding a Node install step at the
top of `build.sh` (Render's docs have a copy-pasteable snippet for this
if it comes to that) — tell me which happened and I'll write the exact
fix rather than guessing preemptively.

## Environment variables to set in Render's dashboard
Required (the app fails loudly at startup if any are missing):
- `DATABASE_URL` — paste your Neon connection string exactly as given,
  no manual editing needed (`shared/config.py` already normalizes
  `postgres://`/`postgresql://` into the `postgresql+psycopg://` form
  the installed driver needs).
- `GROQ_API_KEY`
- `JWT_SECRET`

Needed for the app to be fully functional (not startup-blocking, but
real features won't work without them):
- `FRONTEND_ORIGIN` — in the single-service setup this matters less
  (frontend and backend share an origin in production), but leave it set
  to something sensible; CORS still applies to your local dev setup
  where frontend and backend run as two separate processes.
- `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `GOOGLE_OAUTH_REDIRECT_URI`
  — once you have your Render URL, add `https://your-app.onrender.com/calendar/oauth/callback`
  as a redirect URI in Google Cloud Console, and set
  `GOOGLE_OAUTH_REDIRECT_URI` to that same value here.
- Whatever your email provider needs, once you've picked one.

**Frontend build-time variable** — set this in Render too, since
`build.sh` runs `npm run build` as part of the Render build:
- `VITE_API_BASE_URL` = *(empty string)* — this is the whole point of
  the single-service setup: the frontend calls relative paths like
  `/tasks`, which the browser resolves against whatever origin served
  the page, so no full URL needs to be baked in at all.

## After it's deployed
Full smoke test against the live URL: register, log in, capture
(including voice), complete a task, check Habits/Journal/Planner/
Progress pages, and — once you've set them up — Calendar connect and
password reset.

## On the "clean repo for clients" step
Good instinct to sequence that after deployment is confirmed working,
not before — a README worth showing clients should describe a real,
running app, not an aspirational one. Happy to help write that once
you're at that point; no need to start it now.
