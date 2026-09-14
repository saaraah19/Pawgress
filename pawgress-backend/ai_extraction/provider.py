"""
ai_extraction/provider.py

The Model Provider abstraction. Per System Architecture §10: no module besides
this one, and no API handler, ever calls a model provider's SDK directly. This
is the seam that makes a future provider swap a new class, not a rewrite —
deliberately NOT a generalized multi-provider registry (that was evaluated and
rejected during the spike design phase as speculative infrastructure with no
current second consumer to justify it).

Bounded retry + timeout live here, not in the schema/prompt layers — this is
where "raw single-call behavior" (the spike's own measured numbers) gets a thin,
justified layer of resilience on top, per the approved technical design:
per-request timeout + a small bounded retry, explicitly NOT a full circuit
breaker (no measured traffic yet to justify that infrastructure).
"""

import time
from dataclasses import dataclass
from typing import Optional

from openai import OpenAI

from shared.config import settings
from ai_extraction.prompt import SYSTEM_PROMPT
from ai_extraction.schema import validate_extraction_response, SchemaValidationError, ExtractionResponse
from ai_extraction.cost_logger import log_extraction_call, log_transcription_call


@dataclass
class ExtractionAttemptResult:
    outcome: str  # "success" | "schema_invalid" | "provider_error"
    data: Optional[ExtractionResponse] = None
    raw_response: Optional[str] = None
    error: Optional[str] = None


@dataclass
class TranscriptionAttemptResult:
    outcome: str  # "success" | "provider_error"
    text: Optional[str] = None
    error: Optional[str] = None


class ModelProvider:
    """Interface every concrete provider implements. `transcribe_audio` was
    added 2026-09-13 for voice capture — genuinely a second capability now
    (not speculative surface area the "only one method" comment used to
    warn against), since voice notes are an approved, real V2 feature
    (Engineering Handover §4), not a hypothetical one."""

    def extract_tasks(self, raw_input: str) -> ExtractionAttemptResult:
        raise NotImplementedError

    def transcribe_audio(self, audio_bytes: bytes, filename: str) -> TranscriptionAttemptResult:
        raise NotImplementedError


class GroqModelProvider(ModelProvider):
    """Concrete implementation for Groq's OpenAI-compatible endpoint. Locked
    per the executed spike — see cost_model.md's decision banner."""

    def __init__(self):
        self._client = OpenAI(
            base_url=settings.groq_base_url,
            api_key=settings.groq_api_key,
        )

    def extract_tasks(self, raw_input: str) -> ExtractionAttemptResult:
        # Bounded retry: 1 initial attempt + 1 retry on transient failure.
        # Deliberately small and fixed, not adaptive backoff — the spike's
        # measured p99 (5.74s) doesn't justify more sophisticated resilience
        # yet (System Architecture §1's "don't build ahead of measured need").
        last_error = None
        for attempt in range(2):
            start = time.monotonic()
            try:
                response = self._client.chat.completions.create(
                    model=settings.extraction_model,
                    max_tokens=2000,
                    messages=[
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": raw_input},
                    ],
                    timeout=30.0,
                )
                latency_ms = (time.monotonic() - start) * 1000
                usage = getattr(response, "usage", None)
                input_tokens = getattr(usage, "prompt_tokens", None) if usage else None
                output_tokens = getattr(usage, "completion_tokens", None) if usage else None
                raw_text = response.choices[0].message.content

                try:
                    validated = validate_extraction_response(raw_text)
                    log_extraction_call(
                        model=settings.extraction_model,
                        outcome="success",
                        latency_ms=latency_ms,
                        input_tokens=input_tokens,
                        output_tokens=output_tokens,
                        attempt=attempt,
                    )
                    return ExtractionAttemptResult(outcome="success", data=validated, raw_response=raw_text)
                except SchemaValidationError as e:
                    # Schema-invalid is NOT retried automatically here — a
                    # malformed response on attempt 1 doesn't mean attempt 2
                    # will differ meaningfully, and retrying schema failures
                    # silently risks masking a real prompt/model problem.
                    # It's surfaced as a clean failure instead (System
                    # Architecture §20: partial trust is worse than clean failure).
                    log_extraction_call(
                        model=settings.extraction_model,
                        outcome="schema_invalid",
                        latency_ms=latency_ms,
                        input_tokens=input_tokens,
                        output_tokens=output_tokens,
                        attempt=attempt,
                    )
                    return ExtractionAttemptResult(
                        outcome="schema_invalid", raw_response=raw_text, error=e.reason
                    )
            except Exception as e:
                latency_ms = (time.monotonic() - start) * 1000
                # Provider/network failure — no response, so no token usage
                # to report. Latency and outcome are still real signal
                # (System Architecture §19: tracked per-request regardless
                # of outcome, not just on success).
                log_extraction_call(
                    model=settings.extraction_model,
                    outcome="provider_error",
                    latency_ms=latency_ms,
                    input_tokens=None,
                    output_tokens=None,
                    attempt=attempt,
                )
                last_error = str(e)
                continue  # transient network/provider error — worth one retry

        return ExtractionAttemptResult(outcome="provider_error", error=last_error)

    def transcribe_audio(self, audio_bytes: bytes, filename: str) -> TranscriptionAttemptResult:
        """Voice capture (2026-09-13). Single attempt, no retry — unlike
        extract_tasks, a failed transcription has an immediate, obvious
        fallback already sitting in front of the user (type it instead),
        so the "worth a retry" cost/latency tradeoff that justifies
        extract_tasks's bounded retry doesn't apply the same way here.
        No schema validation step either: Whisper's response is a plain
        transcript string, not structured data with a shape that can be
        "invalid" the way extraction's JSON contract can be."""
        start = time.monotonic()
        try:
            response = self._client.audio.transcriptions.create(
                model=settings.transcription_model,
                file=(filename, audio_bytes),
                timeout=30.0,
            )
            latency_ms = (time.monotonic() - start) * 1000
            text = getattr(response, "text", None)
            if not text or not text.strip():
                # An empty transcript (silence, or a recording that didn't
                # capture speech) is not a provider error — it's a valid,
                # if unhelpful, outcome. Surfaced as success with empty
                # text; the frontend decides how to present "nothing was
                # heard," not this layer.
                log_transcription_call(
                    model=settings.transcription_model, outcome="success", latency_ms=latency_ms, audio_seconds=None
                )
                return TranscriptionAttemptResult(outcome="success", text="")

            log_transcription_call(
                model=settings.transcription_model, outcome="success", latency_ms=latency_ms, audio_seconds=None
            )
            return TranscriptionAttemptResult(outcome="success", text=text.strip())
        except Exception as e:
            latency_ms = (time.monotonic() - start) * 1000
            log_transcription_call(
                model=settings.transcription_model, outcome="provider_error", latency_ms=latency_ms, audio_seconds=None
            )
            return TranscriptionAttemptResult(outcome="provider_error", error=str(e))


def get_model_provider() -> ModelProvider:
    """Single point of construction — nothing outside this module ever
    instantiates a provider directly."""
    return GroqModelProvider()
