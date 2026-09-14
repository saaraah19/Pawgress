"""
tests/test_capture_extraction.py — FR-2.x (AI Inbox capture/extraction),
System Architecture §11 (the synchronous extraction pipeline), FR-2.7
(raw input preservation on failure).

Before this file, the capture/extraction endpoint's own behavior (success,
schema-invalid failure, provider-error failure, the zero-tasks valid case,
raw-text preservation) had NO dedicated test coverage — only its cost-
logging side effect was tested (test_ai_cost_logging.py). Every foundational
doc calls this the single most important interaction in the product; it
was also the least-tested one.

The real Groq provider is never called here — `get_model_provider` is
monkeypatched to return a fake `ModelProvider` per test, exactly the seam
System Architecture §21 describes ("Application/use-case tests... with the
Model Provider abstraction mocked, not calling a real LLM"). No network
access is required or attempted.
"""

import pytest

from ai_extraction.provider import ExtractionAttemptResult
from ai_extraction.schema import ExtractionResponse, ExtractedTask


class FakeProvider:
    """Minimal stand-in for ModelProvider — returns whatever
    ExtractionAttemptResult it was constructed with, regardless of input,
    since these tests are about the endpoint's handling of each outcome,
    not about extraction quality itself (that's the separate,
    non-deterministic golden-set evaluation suite per System Architecture
    §21, not something a unit test should attempt)."""

    def __init__(self, result: ExtractionAttemptResult):
        self._result = result

    def extract_tasks(self, raw_input: str) -> ExtractionAttemptResult:
        return self._result


def _patch_provider(monkeypatch, result: ExtractionAttemptResult):
    import productivity.routes as routes_module

    monkeypatch.setattr(routes_module, "get_model_provider", lambda: FakeProvider(result))


def test_capture_requires_auth(client):
    response = client.post("/captures", json={"rawText": "something"})
    assert response.status_code == 403


def test_successful_extraction_creates_tasks_with_ai_generated_origin(client, auth_headers, monkeypatch):
    """FR-2.2/FR-2.3: multi-task extraction, each field populated; System
    Architecture §11 step 4: capture + tasks returned in ONE response."""
    fake_result = ExtractionAttemptResult(
        outcome="success",
        data=ExtractionResponse(
            tasks=[
                ExtractedTask(title="Finish the statistics course", category="Study", priority="Medium", estimateMinutes=120),
                ExtractedTask(title="Book the dentist", category="Health", priority="Low", estimateMinutes=15),
            ]
        ),
    )
    _patch_provider(monkeypatch, fake_result)

    response = client.post("/captures", json={"rawText": "finish stats course, book dentist"}, headers=auth_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["failureReason"] is None
    assert body["capture"]["status"] == "Succeeded"
    assert len(body["tasks"]) == 2
    assert body["tasks"][0]["title"] == "Finish the statistics course"
    assert all(t["origin"] == "AIGenerated" for t in body["tasks"])


def test_zero_tasks_is_a_valid_success_not_a_failure(client, auth_headers, monkeypatch):
    """extraction_service.py's own docstring: 'Zero tasks is a VALID
    success outcome (a capture that's genuinely just a reflective
    thought) — not treated as failure.'"""
    fake_result = ExtractionAttemptResult(outcome="success", data=ExtractionResponse(tasks=[]))
    _patch_provider(monkeypatch, fake_result)

    response = client.post("/captures", json={"rawText": "just thinking out loud today"}, headers=auth_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["failureReason"] is None
    assert body["capture"]["status"] == "Succeeded"
    assert body["tasks"] == []


def test_schema_invalid_response_is_a_controlled_failure_not_partially_trusted(client, auth_headers, monkeypatch):
    """System Architecture §20: 'Schema-invalid AI responses... are treated
    identically to a provider failure, not partially trusted.' Still a 200
    (the HTTP request itself succeeded; failure is a domain-level outcome,
    not an HTTP error) with an explicit failureReason and zero tasks."""
    fake_result = ExtractionAttemptResult(outcome="schema_invalid", error="missing required field")
    _patch_provider(monkeypatch, fake_result)

    response = client.post("/captures", json={"rawText": "something"}, headers=auth_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["failureReason"] == "schema_invalid"
    assert body["capture"]["status"] == "Failed"
    assert body["tasks"] == []


def test_provider_error_is_a_controlled_failure(client, auth_headers, monkeypatch):
    fake_result = ExtractionAttemptResult(outcome="provider_error", error="timeout")
    _patch_provider(monkeypatch, fake_result)

    response = client.post("/captures", json={"rawText": "something"}, headers=auth_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["failureReason"] == "provider_error"
    assert body["capture"]["status"] == "Failed"


def test_raw_text_is_preserved_on_failure(client, auth_headers, monkeypatch):
    """FR-2.7 / Domain Model Invariant 4 — the whole point of persisting the
    Capture BEFORE calling the provider (extraction_service.py step 1):
    the user's exact original wording must survive a failure untouched, so
    a manual-fallback path always has something real to work from."""
    fake_result = ExtractionAttemptResult(outcome="provider_error", error="timeout")
    _patch_provider(monkeypatch, fake_result)

    raw_text = "the exact messy paragraph the user actually typed, unedited"
    response = client.post("/captures", json={"rawText": raw_text}, headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["capture"]["rawText"] == raw_text


def test_capture_accepts_arbitrary_unstructured_multiline_text(client, auth_headers, monkeypatch):
    """FR-2.1: no formatting/tagging/structuring required of the input."""
    fake_result = ExtractionAttemptResult(outcome="success", data=ExtractionResponse(tasks=[]))
    _patch_provider(monkeypatch, fake_result)

    messy_text = "ok so tomorrow i need to\n\ndo the thing with the taxes maybe??\nand also. call mom. ugh"
    response = client.post("/captures", json={"rawText": messy_text}, headers=auth_headers)
    assert response.status_code == 200


def test_transcribe_requires_auth(client):
    response = client.post("/captures/transcribe", files={"file": ("note.webm", b"fake-audio-bytes", "audio/webm")})
    assert response.status_code == 403


def test_transcribe_returns_text_on_success(client, auth_headers, monkeypatch):
    from ai_extraction.provider import TranscriptionAttemptResult

    class FakeProvider:
        def transcribe_audio(self, audio_bytes, filename):
            return TranscriptionAttemptResult(outcome="success", text="finish the statistics course")

    import productivity.routes as routes_module

    monkeypatch.setattr(routes_module, "get_model_provider", lambda: FakeProvider())

    response = client.post(
        "/captures/transcribe",
        files={"file": ("note.webm", b"fake-audio-bytes", "audio/webm")},
        headers=auth_headers,
    )
    assert response.status_code == 200
    assert response.json()["text"] == "finish the statistics course"


def test_transcribe_failure_is_a_clean_error_not_a_silent_empty_result(client, auth_headers, monkeypatch):
    """System Architecture §20's philosophy extended to transcription: a
    provider failure is surfaced honestly, not disguised as an empty
    transcript (which would look like 'nothing was said' rather than
    'something went wrong')."""
    from ai_extraction.provider import TranscriptionAttemptResult

    class FakeProvider:
        def transcribe_audio(self, audio_bytes, filename):
            return TranscriptionAttemptResult(outcome="provider_error", error="timeout")

    import productivity.routes as routes_module

    monkeypatch.setattr(routes_module, "get_model_provider", lambda: FakeProvider())

    response = client.post(
        "/captures/transcribe",
        files={"file": ("note.webm", b"fake-audio-bytes", "audio/webm")},
        headers=auth_headers,
    )
    assert response.status_code == 502


def test_transcribe_rejects_empty_upload(client, auth_headers):
    response = client.post(
        "/captures/transcribe", files={"file": ("note.webm", b"", "audio/webm")}, headers=auth_headers
    )
    assert response.status_code == 422


def test_transcribe_rejects_oversized_upload(client, auth_headers):
    import productivity.routes as routes_module

    oversized = b"x" * (routes_module.MAX_AUDIO_UPLOAD_BYTES + 1)
    response = client.post(
        "/captures/transcribe", files={"file": ("note.webm", oversized, "audio/webm")}, headers=auth_headers
    )
    assert response.status_code == 413


def test_created_tasks_are_scoped_to_the_capturing_user(client, auth_headers, second_user_headers, monkeypatch):
    """Every task created from a capture must be owned by the same user who
    submitted it — System Architecture §9's authorization rule, applied to
    the one write path that creates tasks on the user's behalf rather than
    from a direct user action."""
    fake_result = ExtractionAttemptResult(
        outcome="success",
        data=ExtractionResponse(tasks=[ExtractedTask(title="Only mine", category="Misc", priority="Medium")]),
    )
    _patch_provider(monkeypatch, fake_result)

    client.post("/captures", json={"rawText": "only mine"}, headers=auth_headers)

    other_users_tasks = client.get("/tasks", headers=second_user_headers).json()
    assert all(t["title"] != "Only mine" for t in other_users_tasks)
