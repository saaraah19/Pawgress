"""
productivity/extraction_service.py

Domain Model §10.1: "Takes a Capture's raw input, calls the AI provider, and
produces zero or more draft Task field-sets... Responsible for populating
Capture's status and, on success, creating the resulting Task entities."

This is the ONE place Productivity Core is allowed to call into AI/Extraction —
System Architecture §6: "synchronous in-process calls for anything in the
request path." Nothing else in this module touches ai_extraction directly.
"""

import uuid
from sqlalchemy.orm import Session

from productivity.models import Capture, Task, CaptureStatus, TaskOrigin, Priority
from ai_extraction.provider import ModelProvider


class ExtractionResult:
    """What the API layer needs to build its response — deliberately distinct
    from the raw ExtractionAttemptResult, since this carries the *persisted*
    Capture/Tasks, not just the provider's raw answer."""

    def __init__(self, capture: Capture, tasks: list[Task], failure_reason: str | None = None):
        self.capture = capture
        self.tasks = tasks
        self.failure_reason = failure_reason  # "schema_invalid" | "provider_error" | None


def run_extraction(db: Session, user_id: uuid.UUID, raw_text: str, provider: ModelProvider) -> ExtractionResult:
    """
    The core Slice 1 flow, matching System Architecture §11 exactly:

    1. Capture is created and committed BEFORE extraction is attempted — this
       is the literal mechanical enforcement of "raw input is never lost"
       (Domain Model Invariant 4). The raw text is safe the instant this
       function is called, regardless of what happens next.
    2. ExtractionService calls the Model Provider.
    3a. On success: Capture -> Succeeded, Tasks created with Origin=AIGenerated,
        source_capture_id set. Zero tasks is a VALID success outcome (a capture
        that's genuinely just a reflective thought) — not treated as failure.
    3b. On schema_invalid or provider_error: Capture -> Failed. Raw text is
        untouched — it was already committed in step 1 and this function never
        writes to Capture.raw_text again.
    """
    # Step 1 — persist raw input first, unconditionally.
    capture = Capture(
        id=uuid.uuid4(),
        user_id=user_id,
        raw_text=raw_text,
        status=CaptureStatus.PENDING,
    )
    db.add(capture)
    db.commit()
    db.refresh(capture)

    # Step 2 — call the provider.
    result = provider.extract_tasks(raw_text)

    # Step 3a — success (including the valid zero-tasks case).
    if result.outcome == "success":
        capture.status = CaptureStatus.SUCCEEDED
        created_tasks = []
        for extracted in result.data.tasks:
            task = Task(
                id=uuid.uuid4(),
                user_id=user_id,
                title=extracted.title,
                category=extracted.category,
                priority=Priority(extracted.priority),
                estimate_minutes=extracted.estimateMinutes,
                origin=TaskOrigin.AI_GENERATED,
                source_capture_id=capture.id,
            )
            db.add(task)
            created_tasks.append(task)
        db.commit()
        for t in created_tasks:
            db.refresh(t)
        return ExtractionResult(capture=capture, tasks=created_tasks, failure_reason=None)

    # Step 3b — schema_invalid or provider_error. Capture.raw_text is never
    # touched here — only status changes (Domain Model Invariant 4).
    capture.status = CaptureStatus.FAILED
    db.commit()
    db.refresh(capture)
    return ExtractionResult(capture=capture, tasks=[], failure_reason=result.outcome)
