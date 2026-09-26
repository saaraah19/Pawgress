"""
main.py — Pawgress backend entrypoint.

Wires the Identity, Productivity Core, and Companion routers together.
Deliberately thin — this file's only job is app setup; all real logic lives
in the modules.

Single-service deployment (2026-09-16): also serves the built React
frontend as static files, so the whole app is one Render web service
instead of two — no separate frontend host, no CORS between them (same
origin), and only one URL to register as the Google OAuth redirect. The
tradeoff, worth remembering later: backend and frontend now deploy
together as one unit rather than independently. Fine for a solo project
with no scaling need right now; if that ever changes, splitting them back
into two services is straightforward since nothing about the API routes
themselves depends on this.
"""

import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from shared.config import settings
from identity.routes import router as identity_router
from productivity.routes import router as productivity_router
from companion.routes import router as companion_router
from journal.routes import router as journal_router
from habits.routes import router as habits_router
from calendar_integration.routes import router as calendar_router
from planner.routes import router as planner_router
from gamification.routes import router as gamification_router

settings.validate()  # fail loudly at startup if required env vars are missing

# System Architecture §19: three log categories kept structurally separate
# (operational, product metrics, AI cost/performance). This call only
# ensures the "pawgress.ai_cost" logger (ai_extraction/cost_logger.py) has
# somewhere to go in local dev — stdout, one JSON object per line, easy to
# grep or pipe into a real log processor later without changing the
# emitting code at all.
logging.basicConfig(level=logging.INFO, format="%(message)s")

app = FastAPI(title="Pawgress API", version="0.2.0-slice2")

# Scoped to the configured frontend origin(s) (default: local Vite dev
# server, both localhost and 127.0.0.1 variants). See shared/config.py's
# FRONTEND_ORIGIN — set this explicitly for any real deployment rather than
# relying on the local-dev default. Still needed even in the single-service
# deployment: local dev still runs frontend and backend as two separate
# processes on two different ports, so cross-origin requests still happen
# there. In production, frontend and backend share an origin and this
# middleware simply never has anything to reject.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.frontend_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(identity_router)
app.include_router(productivity_router)
app.include_router(companion_router)
app.include_router(journal_router)
app.include_router(habits_router)
app.include_router(calendar_router)
app.include_router(planner_router)
app.include_router(gamification_router)


@app.get("/health")
def health_check():
    return {"status": "ok"}


# --- Serve the built frontend, if present (2026-09-16) ---
# STATIC_DIR only exists once the Render build command has actually built
# the frontend and copied its `dist/` output here (see the deploy
# instructions) — it's absent in local dev, where Vite's own dev server
# serves the frontend instead. Registered LAST and deliberately: every
# route above is more specific than the catch-all below, and FastAPI/
# Starlette match routes in registration order, so a real API path (even
# one that 404s for its own reasons, like an unknown task id) is always
# resolved by its own router first — this catch-all only ever sees paths
# that no API router claimed at all, i.e. the frontend's own client-side
# routes (/planner, /goals, etc.) when someone loads them directly instead
# of navigating there from within the app.
STATIC_DIR = Path(__file__).parent / "static"

if STATIC_DIR.is_dir():
    app.mount("/assets", StaticFiles(directory=STATIC_DIR / "assets"), name="static-assets")

    @app.get("/{full_path:path}")
    async def serve_frontend(full_path: str):
        candidate = STATIC_DIR / full_path
        if full_path and candidate.is_file():
            # A root-level static file Vite emits outside /assets (e.g.
            # favicon.ico) — served directly rather than falling through
            # to index.html.
            return FileResponse(candidate)
        # Any real frontend route, and genuinely unknown paths alike, all
        # get the SPA shell — React Router decides from there what to
        # actually show, exactly like any other static SPA host would
        # behave.
        return FileResponse(STATIC_DIR / "index.html")
