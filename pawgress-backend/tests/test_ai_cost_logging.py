"""
tests/test_ai_cost_logging.py — System Architecture §19: AI cost/performance
metrics tracked per-request, structurally separate from other log
categories, never containing raw user content.

Tests the logger in isolation (no live provider call — consistent with the
existing pattern of stubbing ModelProvider rather than hitting Groq in
tests, see tests/test_task_deletion.py).
"""

import json
import logging

from ai_extraction.cost_logger import log_extraction_call


def test_log_extraction_call_emits_structured_record(caplog):
    with caplog.at_level(logging.INFO, logger="pawgress.ai_cost"):
        log_extraction_call(
            model="openai/gpt-oss-120b",
            outcome="success",
            latency_ms=842.3,
            input_tokens=568,
            output_tokens=120,
            attempt=0,
        )

    assert len(caplog.records) == 1
    record = json.loads(caplog.records[0].message)

    assert record["event"] == "extraction_call"
    assert record["model"] == "openai/gpt-oss-120b"
    assert record["outcome"] == "success"
    assert record["latency_ms"] == 842.3
    assert record["input_tokens"] == 568
    assert record["output_tokens"] == 120
    assert record["attempt"] == 0
    assert "timestamp" in record


def test_log_extraction_call_never_includes_raw_content(caplog):
    """§17/§19's hard rule: raw Capture text and Task titles are never
    logged at standard verbosity. This is a structural test, not just a
    convention — log_extraction_call's signature has no parameter that
    could carry raw text in the first place, but this test guards against
    a future edit accidentally threading one through."""
    with caplog.at_level(logging.INFO, logger="pawgress.ai_cost"):
        log_extraction_call(
            model="openai/gpt-oss-120b",
            outcome="provider_error",
            latency_ms=30000.0,
            input_tokens=None,
            output_tokens=None,
            attempt=1,
        )

    record = json.loads(caplog.records[0].message)
    allowed_keys = {"event", "timestamp", "model", "outcome", "latency_ms", "input_tokens", "output_tokens", "attempt"}
    assert set(record.keys()) == allowed_keys
    assert record["input_tokens"] is None
    assert record["output_tokens"] is None
