"""
main.py — Pawgress backend entrypoint.

Wires the Identity, Productivity Core, and Companion routers together.
Deliberately thin — this file's only job is app setup; all real logic lives
in the modules.
"""

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from shared.config import settings
from identity.routes import router as identity_router
from productivity.routes import router as productivity_router
from companion.routes import router as companion_router
from journal.routes import router as journal_router
from habits.routes import router as habits_router
from calendar_integration.routes import router as calendar_router

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
# relying on the local-dev default.
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


@app.get("/health")
def health_check():
    return {"status": "ok"}
