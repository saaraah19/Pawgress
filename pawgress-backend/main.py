"""
main.py — Pawgress backend entrypoint.

Wires the Identity, Productivity Core, and Companion routers together.
Deliberately thin — this file's only job is app setup; all real logic lives
in the modules.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from shared.config import settings
from identity.routes import router as identity_router
from productivity.routes import router as productivity_router
from companion.routes import router as companion_router

settings.validate()  # fail loudly at startup if required env vars are missing

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


@app.get("/health")
def health_check():
    return {"status": "ok"}
