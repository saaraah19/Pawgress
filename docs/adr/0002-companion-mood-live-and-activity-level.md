# ADR 0002: Cat Companion mood — computed live, activity-level not capture-specific

**Status:** Accepted
**Date:** 2026-08-03
**Context:** Cat Companion UI slice (`GET /companion/state` + frontend
indicator). Two deliberate deviations from a literal reading of the
foundational documents, made explicitly rather than discovered later.

---

## Decision 1: `CatMoodState` is computed live, not persisted as its own table

**What the Domain Model describes (§4.5):** `CatCompanionState` as an
entity — "part of the User aggregate," with attributes "owning User
identifier, current mood state (enum), last updated timestamp." Read
literally, this implies a `cat_companion_states` table with a row per user.

**What this implementation does instead:** no such table exists.
`companion/mood_calculator.py::calculate_mood()` derives the mood on every
request, directly from `Task`/`Capture` rows that already exist for other
reasons. There is no `last updated timestamp` anywhere, because nothing is
ever written.

**Why:** §4.5 itself frames the *reason* CatCompanionState is modeled as
current-value-only: to prevent it from becoming "a hidden state machine or
scoring system" — a history table would be "the first quiet step toward
exactly the kind of gamification-by-the-back-door the Blueprint warns
against." A persisted-but-current-value-only table gets most of the way
there, but it's still a write path, a migration, and a staleness question
("when do we recompute it — on every Task change? on a schedule?") for a
value that's already fully and cheaply derivable at read time from data
that's persisted anyway. Computing it live satisfies the *intent* of §4.5
(minimal, non-scoring, presentation-only) more conservatively than a table
would, at the cost of one small extra query per request — a real cost, but
a bounded and cheap one at MVP scale (System Architecture §15's "no
caching layer for MVP" reasoning applies here for the same reason: no
current, measured need justifies the extra moving part).

**What this means for Companion/Productivity-Core isolation (Domain Model
§3):** the isolation still holds — `companion/mood_calculator.py` *reads*
`Task`/`Capture`, exactly as Domain Model §10.2 specifies for
CatMoodStateCalculator ("reads from Task/Capture history, but never writes
to them... structurally one-directional"). Nothing in `productivity/`
imports from `companion/`. The only change from a literal §4.5 reading is
*where* the current value lives (computed, not stored) — the *behavior*
Domain Model requires (current-value-only, one-directional read, no
history) is unchanged.

**Tradeoff, named plainly:** if a future feature genuinely needs the
*history* of mood changes (not currently planned — Domain Model §13
explicitly defers this), this decision would need revisiting; a live
computation can't retroactively produce a history that was never recorded.
That's an acceptable bet given §13's own framing that mood history is a
deliberate future decision, not an oversight to guard against now.

**Revisit if:** the mood calculation becomes expensive enough (e.g. once
real behavioral-history reasoning is added in a later Companion iteration)
that computing it on every request stops being cheap — at that point,
caching the derived value (not modeling it as a full history) would be the
next step, not a wholesale table redesign.

---

## Decision 2: The cat's reaction is activity-level, not capture-specific

**What FR-2.6 describes:** "If the cat companion produces any reaction to a
capture, that reaction shall reference something concrete from the
specific capture just made, rather than a generic/stock reaction" —
i.e., a reaction tied to *this particular capture's content*.

**What this implementation does instead:** the Companion indicator reflects
recent *activity in general* (any capture or task today vs. ever vs.
never) — it has no awareness of what a specific capture said, and renders
identically regardless of which capture just happened.

**Why:** a genuinely capture-specific reaction requires generating
content *about* that capture — effectively a second AI call reasoning over
the just-extracted structure, which is real scope and real cost (Business
Model §5's cost-tiering principle: this would be a second inference call
on every free-tier capture, not the cheap read this ADR's first decision
depends on). It's also adjacent to Coach/insight territory that MVP
Definition §5 and Blueprint §13 explicitly defer to Version 2 — reasoning
about "what does this specific capture mean" is a different capability
than "is there recent activity," and the MVP's approved scope (Domain
Model §13, Handover §6) doesn't include a per-capture-reasoning AI call
anywhere.

**What this means for FR-2.6/BR-3 specifically:** FR-2.6 as literally
written is not fully satisfied by this implementation. BR-3 ("the cat
shall not be the primary visual focus of the First Capture moment") *is*
satisfied — the indicator lives in the app header, not in the capture
result view at all, so it can't compete with the extraction result for
attention. The gap is narrower than it might first read: FR-2.6 only
applies "if the cat companion produces any reaction to a capture" — this
implementation doesn't produce a capture-triggered reaction at all, it
produces an always-present ambient state, which sidesteps the requirement
rather than satisfying it.

**Revisit if:** Sarah wants true per-capture cat reactions — that's a
real, separate feature (a small, cheap-model call reasoning over the
just-extracted tasks to produce one short phrase), not a tweak to this
implementation, and should be scoped and costed as its own slice rather
than folded into "add a mood indicator."
