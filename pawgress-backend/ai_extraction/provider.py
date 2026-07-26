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

from dataclasses import dataclass
from typing import Optional

from openai import OpenAI

from shared.config import settings
from ai_extraction.prompt import SYSTEM_PROMPT
from ai_extraction.schema import validate_extraction_response, SchemaValidationError, ExtractionResponse


@dataclass
class ExtractionAttemptResult:
    outcome: str  # "success" | "schema_invalid" | "provider_error"
    data: Optional[ExtractionResponse] = None
    raw_response: Optional[str] = None
    error: Optional[str] = None


class ModelProvider:
    """Interface every concrete provider implements. Only one method, because
    that's the only thing the current use case needs — no speculative surface
    area for capabilities (coaching, memory formation) that don't exist yet."""

    def extract_tasks(self, raw_input: str) -> ExtractionAttemptResult:
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
                raw_text = response.choices[0].message.content
                try:
                    validated = validate_extraction_response(raw_text)
                    return ExtractionAttemptResult(outcome="success", data=validated, raw_response=raw_text)
                except SchemaValidationError as e:
                    # Schema-invalid is NOT retried automatically here — a
                    # malformed response on attempt 1 doesn't mean attempt 2
                    # will differ meaningfully, and retrying schema failures
                    # silently risks masking a real prompt/model problem.
                    # It's surfaced as a clean failure instead (System
                    # Architecture §20: partial trust is worse than clean failure).
                    return ExtractionAttemptResult(
                        outcome="schema_invalid", raw_response=raw_text, error=e.reason
                    )
            except Exception as e:
                last_error = str(e)
                continue  # transient network/provider error — worth one retry

        return ExtractionAttemptResult(outcome="provider_error", error=last_error)


def get_model_provider() -> ModelProvider:
    """Single point of construction — nothing outside this module ever
    instantiates a provider directly."""
    return GroqModelProvider()
