# ADR 0001: Goal deletion enforcement, required secrets, and CORS scoping

**Status:** Accepted
**Date:** 2026-08-03
**Context:** Manual Task Creation UI slice. While implementing FR-3.4, the
Slice 2 backend surface the frontend already depended on (`POST /tasks`,
`DELETE /tasks/{id}`, `/goals` CRUD, `goal_id` on Task) turned out to be
missing from the repository entirely, despite the frontend already calling
it. This ADR documents the decisions made rebuilding that surface, not just
the manual-creation endpoint itself.

---

## Decision 1: Goal deletion is unlinked in application code, not via DB-level cascade

**Decision:** `DELETE /goals/{id}` is implemented as an explicit two-step
application-layer operation (`productivity/goal_service.py`:
`delete_goal_and_unlink_tasks`) — set every referencing `Task.goal_id` to
`NULL`, then delete the `Goal` row, committed as one unit of work. The
`Task.goal_id` foreign key has **no** `ON DELETE CASCADE` or
`ON DELETE SET NULL` at the schema level.

**Why:** Domain Model §9 Invariant 9 and §10.5 (GoalDeletionService) require
that deleting a Goal *never* deletes or cascades to linked Tasks — only
unlinks them. A DB-level `ON DELETE CASCADE` would delete the Tasks outright
(wrong). `ON DELETE SET NULL` would get the *outcome* right but makes the
invariant implicit in schema DDL rather than an explicit, testable, readable
operation — and it would silently keep being "correct" even if some future
code path deleted a Goal by a route other than this service (e.g. a bulk
admin script), which is exactly the kind of accidental-correctness that's
fragile to depend on long-term. Keeping the unlink in application code makes
Invariant 9 enforced by one deliberate function, verified directly by
`tests/test_goals.py::test_deleting_goal_unlinks_but_does_not_delete_linked_tasks`.

**Alternative considered:** `ON DELETE SET NULL` at the FK level. Rejected —
correct outcome, wrong place for the invariant to live; couples a domain
rule to schema DDL instead of to the domain service the Domain Model already
names for this purpose.

**Revisit if:** Goal deletion volume ever becomes a real performance
concern at a scale where a DB-level operation would meaningfully outperform
the two-query application-level version. Not expected at MVP scale.

---

## Decision 2: `JWT_SECRET` has no insecure fallback; it's required at startup

**Decision:** `shared/config.py` no longer falls back to
`"dev-only-insecure-secret-change-me"` when `JWT_SECRET` is unset.
`Settings.validate()` now treats it exactly like `DATABASE_URL` and
`GROQ_API_KEY` — startup fails loudly if it's missing.

**Why:** The insecure fallback value was public in source control the whole
time — anyone who could read the repository could forge a valid session
token for any user. The file's own prior comment already said "never use
the fallback below outside local development," which is an easy rule to
violate by accident (e.g. forgetting to set the env var in a deployed
environment) and impossible to violate once the fallback doesn't exist.

**Tradeoff:** Local development now requires generating and setting a
`JWT_SECRET` explicitly (documented in `.env.example`) — a small, one-time
DX cost in exchange for removing a real security hole.

---

## Decision 3: CORS is scoped to a single configured `FRONTEND_ORIGIN`

**Decision:** `main.py`'s `CORSMiddleware` now uses
`allow_origins=[settings.frontend_origin]` (default:
`http://127.0.0.1:5173`, matching Vite's local dev server and the
`127.0.0.1`-not-`localhost` note already established for
`VITE_API_BASE_URL`) instead of `allow_origins=["*"]`.

**Why:** System Architecture §17's least-privilege principle, applied to
the browser boundary. A wildcard origin combined with bearer-token auth
sent from arbitrary origins is a real, unnecessary attack surface once this
is deployed anywhere beyond a single developer's machine.

**Revisit if:** Multiple frontend origins need to be supported
simultaneously (e.g. staging + production served from different hosts) —
`frontend_origin` would need to become a list at that point. Not needed yet.

---

## Decision 4: `FieldCorrectionRecord` tracking stays scoped to exactly four AI-assigned fields

**Decision:** `TaskUpdateRequest` gained `status` and `goalId` (both needed
for already-approved FR-3.3/FR-5.2 behavior to actually function — this was
a contract omission, not a new capability). `routes.py` introduces an
explicit `CORRECTION_TRACKED_FIELDS = {"title", "category", "priority",
"estimateMinutes"}` constant so the correction-tracking loop only fires
FieldCorrectionRecord writes for genuine AI-field corrections, never for a
status toggle (Completing-and-Reflecting, UX Philosophy §5.3) or a goal link
(Discovering Goal-Linking, UX Philosophy §5.4).

**Why:** Domain Model §10.3 defines CorrectionTracker as firing "whenever a
user changes an AI-assigned field." Marking a task Done or linking it to a
goal is not a correction — writing a FieldCorrectionRecord for either would
quietly inflate Blueprint §17's correction-rate metric with events that
aren't actually about AI accuracy, corrupting the one number the product
most depends on being trustworthy.

**Verified by:** `tests/test_task_correction_scope.py`.
