"""
main.py — Pawgress backend entrypoint.

Wires the Identity and Productivity Core routers together. Deliberately thin —
this file's only job is app setup; all real logic lives in the modules.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from shared.config import settings
from identity.routes import router as identity_router
from productivity.routes import router as productivity_router

settings.validate()  # fail loudly at startup if required env vars are missing

app = FastAPI(title="Pawgress API", version="0.1.0-slice1")

# Permissive for local development. Tighten to the real frontend origin
# before any real deployment beyond local testing.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(identity_router)
app.include_router(productivity_router)


@app.get("/health")
def health_check():
    return {"status": "ok"}
