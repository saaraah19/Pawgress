"""
ai_extraction/cost_logger.py

Direct implementation of System Architecture §19: "AI cost/performance
metrics (tokens used, latency per provider call, model tier used) —
tracked per-request from day one... this needs to exist before it's
urgent, not after." Also implements §19's explicit separation rule: this
is its own log category, never mixed with operational logs or product
metrics, and — per §17/§19's hard rule — never includes raw user content
(Capture text, Task titles) at any verbosity.

Mechanism, and why it's a log line rather than a database table
(a technical recommendation, not something any document mandates):
no foundational document asks for these metrics to be queryable through
the product (no in-app cost dashboard is in MVP scope, Domain Model §13),
so a DB table would be new domain-adjacent surface area — a migration, a
BR-10 deletion-guarantee obligation if any field is ever user-linked, a
retention policy — for a requirement that's satisfied by "tracked
per-request," not "queryable per-request." A structured log line is the
smallest correct implementation per System Architecture §1's governing
constraint, and the schema below is deliberately table-shaped (flat,
named fields) so promoting this to a real table or a log-shipping
pipeline later is a mechanical change, not a redesign. See
docs/adr/0003-ai-cost-logging-as-structured-logs-not-a-table.md.

This module owns exactly one job: emit one structured record per
extraction attempt. It does not read config for where logs go (stdout is
fine for MVP local dev — see main.py's logging.basicConfig call) and does
not know about retries, HTTP, or the provider SDK; ai_extraction/provider.py
calls this once per attempt.
"""

import json
import logging
import time
from typing import Optional

logger = logging.getLogger("pawgress.ai_cost")


def log_extraction_call(
    *,
    model: str,
    outcome: str,  # "success" | "schema_invalid" | "provider_error"
    latency_ms: float,
    input_tokens: Optional[int],
    output_tokens: Optional[int],
    attempt: int,  # 0-indexed — which retry attempt this was
) -> None:
    """Emits one structured JSON log line. Deliberately narrow: only the
    fields System Architecture §19 actually names (tokens, latency, model
    tier) plus the outcome/attempt needed to make the numbers meaningful.
    No user id, no raw text, no task content — this is a cost/performance
    signal, not an audit trail of what anyone captured."""
    record = {
        "event": "extraction_call",
        "timestamp": time.time(),
        "model": model,
        "outcome": outcome,
        "latency_ms": round(latency_ms, 1),
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "attempt": attempt,
    }
    logger.info(json.dumps(record))


def log_transcription_call(
    *,
    model: str,
    outcome: str,  # "success" | "provider_error"
    latency_ms: float,
    audio_seconds: Optional[float],
) -> None:
    """Voice capture's equivalent of log_extraction_call — kept as a
    separate event name ("transcription_call") rather than reusing
    log_extraction_call with a relabeled outcome, since mixing the two
    under one event name would make cost-per-feature analysis (Business
    Model §5, now with a second AI-cost-bearing feature) harder to read
    later, not easier. Same content rules apply: no user id, no audio, no
    transcript text — cost/performance signal only."""
    record = {
        "event": "transcription_call",
        "timestamp": time.time(),
        "model": model,
        "outcome": outcome,
        "latency_ms": round(latency_ms, 1),
        "audio_seconds": audio_seconds,
    }
    logger.info(json.dumps(record))
