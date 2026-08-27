# Pawgress — Project Progress

**Last updated:** 2026-08-22, frontend test infrastructure — done.

This file is the single place to check "where are we right now" without
re-deriving it from chat history. Updated at the end of every slice —
whoever picks this up next (human or Claude instance) should be able to
read this file alone and know exactly what's done, what's in flight, and
what's next.

---

## 🔴 One manual step only Sarah can do — required before Calendar works for real

Everything in Slice E is built, tested, and verified against real
PostgreSQL — **except the one thing no automated test in this
environment can prove**: the actual live OAuth handshake against
Google's real servers. This sandbox has no network path to
`accounts.google.com`, so this was verified with a stub provider instead
(proves the routing/persistence/error-handling logic is correct, not that
the real Google integration works end-to-end).

**Before Calendar can be used for real, Sarah needs to:**
1. Create an OAuth 2.0 Client ID (type: "Web application") in Google
   Cloud Console, under APIs & Services > Credentials.
2. Enable the Google Calendar API for that project.
3. Add an authorized redirect URI that **exactly** matches
   `GOOGLE_OAUTH_REDIRECT_URI` (default `http://127.0.0.1:8000/calendar/oauth/callback`
   for local dev) — scheme, host, port, and path all have to match
   exactly, or Google will reject the callback.
4. While the OAuth consent screen is in "Testing" mode (the default for
   a new project), add her own Google account as a test user, or Google
   will block the consent screen entirely.
5. Set `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, and (if not using the
   default) `GOOGLE_OAUTH_REDIRECT_URI` in her real `.env`.
6. Run the app locally and click through the real "Connect Google
   Calendar" flow once, with her own real calendar, to confirm events
   actually appear.

Calendar is opt-in — the rest of the app runs completely normally without
any of this done; `/calendar/oauth/start` just returns a clear 503
("Google Calendar isn't configured") until it is.

---

## Just Completed: Frontend Test Infrastructure (2026-08-22)

Sarah's call, asked for directly: five slices in a row had flagged "no
frontend automated tests" as a real, named gap, and with Calendar/DB
migration both blocked on her own manual steps, this was the highest-
value non-blocking thing to spend the time on — closes a compounding
risk rather than adding more untested surface on top of an already-large
pile.

**Stack:** Vitest + `@testing-library/react` + `jsdom`. One real
integration snag, worth knowing about: the first install pulled Vitest
2.x, which doesn't officially support Vite 6 — npm silently resolved a
*nested, duplicate* Vite 5 copy just for Vitest's own internal use, which
then caused a genuine TypeScript conflict (two structurally-identical but
nominally-different `Plugin` types from two different Vite copies in the
dependency tree) as soon as `vite.config.ts` tried to share its `plugins`
array with Vitest's `test` config block. Fixed correctly by upgrading to
Vitest 3.x (which does support Vite 6), not by suppressing the type error
— confirmed afterward that no nested Vite copy exists in `node_modules`
anymore.

**Config:** `vite.config.ts` now has a `test` block (jsdom environment,
`src/setupTests.ts` as the setup file) rather than a separate
`vitest.config.ts` — one config file, since there was no real reason to
split it once the Vite-version conflict was actually fixed. `globals:
true` was deliberately NOT enabled — test files import
`describe`/`it`/`expect`/etc. explicitly from `"vitest"` rather than
relying on ambient globals, avoiding any change to `tsconfig.app.json`'s
type declarations that could otherwise bleed into the app's own
production type-checking scope. `src/setupTests.ts` adds jest-dom's
matchers and a `window.matchMedia` polyfill (jsdom doesn't implement it
at all, and real code — `useCompanionBehavior`'s reduced-motion check —
calls it directly).

**Scripts added:** `npm test` (run once), `npm run test:watch`, `npm run
test:coverage`.

**First real tests written** (not placeholder smoke tests — picked the
two pieces of frontend logic complex enough to actually be worth
protecting):
- `features/goals/goalHierarchy.test.ts` — 11 tests covering the pure
  tree-building and eligible-parent logic: untiered goals never enter the
  forest, multi-level nesting, a Milestone attaching directly to an
  Annual (skipping intermediate tiers), the orphaned-parent fail-safe,
  and every eligibility-filtering rule (no self-parenting, no
  same-or-narrower tier, any strictly-broader tier qualifies).
- `features/companion/useCompanionBehavior.test.ts` — 10 tests covering
  all four behavior layers using Vitest's fake timers plus a mocked
  `Math.random` (pinned to `0`, which makes `pickWeighted` deterministic
  — it always returns the first key in whichever weight table is being
  drawn from): mood-driven expression selection, immediate reroll on
  mood change, the independent reroll cadence, `reactToCapture`'s
  temporary override and revert, `reactToCapture` correctly no-op'ing
  while already active, ambient animation scheduling, ambient animations
  being fully skipped (not just CSS-suppressed) under
  `prefers-reduced-motion`, `triggerEarnedDelight` confirmed as a true
  no-op, and clean unmount.

**A real bug caught in my own first draft of these tests, not in the
app code:** an early version of the ambient-animation test asserted the
final state after advancing time by `ambientMaxMs + 1000`, but the
ambient animation is deliberately *transient* — it clears itself again
900ms after triggering. That specific time delta happened to land right
after a clear-and-reschedule cycle had already fired, so the assertion
failed even though the hook's actual behavior was correct. Diagnosed with
a temporary debug test rather than guessing, then fixed by asserting at
the actual trigger point instead of an arbitrary later moment — a good
reminder that transient/pulsing state needs tests that check timing
precisely, not just "did enough time pass."

**Verified:** clean-room `node_modules` reinstall from the committed
lockfile, then `tsc -b` (clean), `npm test` (21/21 passing), `npm run
build` (clean, same module count and asset sizes as before — confirming
test files don't leak into the production bundle).

**What this does NOT include, stated plainly:** no tests yet for any
page-level component (`CapturePage`, `GoalsPage`, `JournalPage`,
`HabitsPage`, `CalendarPage`, `AppShell`) or for `CompanionCharacter`'s
actual rendering/crossfade behavior — only the two pure-logic/hook
modules above. The infrastructure is real and proven; broad coverage
across the rest of the frontend is not there yet and would be a
reasonable next investment, not a claim being made now.

---

## Phase

**V2 development, pulled forward from the Polish Sprint (2026-08-16).**
Sarah made a deliberate call: rather than continue polishing the MVP,
start building toward the bigger vision (Blueprint §13 V2/Long-Term) —
full goal hierarchy, then eventually Habits, Journal, Calendar, and
(once real usage history exists) Weekly Reviews/Coach/Memory. Final
polish items — including the companion-placement idea below — are
explicitly LAST, after V2 substance, not abandoned.

**Standing authorization from Sarah for this V2 work specifically:**
proceed through slices without stopping for confirmation at each step.
Only pause to ask when there's genuine ambiguity, real uncertainty, or
something critical (security, an expensive-to-reverse schema/architecture
decision, or a real document contradiction). This supersedes the stricter
Polish-Sprint "stop after every slice" discipline for V2 work — but
docs/PROGRESS.md still gets updated as slices land, and tests still get
written and run before anything is called done.

**V2 readiness assessment** (done 2026-08-15, still accurate): full goal
hierarchy and Journal are buildable today with no blockers. Habits needs
real non-punitive-streak design work first (Blueprint §16 warns explicitly
against a naive version) — not just a build. Calendar is the heaviest lift
(external OAuth/API). Weekly Reviews / pattern detection / AI Coach are
**not honestly buildable yet** — there's no real usage history to reason
over, and the docs are explicit that shipping insight from insufficient
data is a trust violation, not just a rough edge (Blueprint §5, §16).

---

## Just Completed: Alembic Baseline (Slice A) + Full Goal Hierarchy (Slice B)

### Slice A — Alembic baseline, zero functional change

Replaced the "hand-typed ALTER TABLE" workflow with real, versioned
migrations. `alembic/env.py` is wired to `shared/config.py`'s
`DATABASE_URL` and `shared/database.py`'s `Base` (same pattern as every
other module — no hardcoded connection string, no separate metadata
definition that could drift from the real models).

One baseline migration (`a6bf4696c8da_baseline_schema.py`) captures the
real, current 5-table schema (`users`, `captures`, `goals`, `tasks`,
`field_correction_records`) exactly — generated by autogenerating against
a genuinely empty database, not a stamp-only artifact, so it also works as
a real from-scratch setup path for a new environment.

**Verified, not assumed** (full log below, this was a real up/down/up
round-trip against actual PostgreSQL 16, not SQLite):
- `alembic upgrade head` against empty → creates the exact real schema.
- A second `--autogenerate` immediately after comes back completely empty
  — proof the migration is a byte-for-byte match of the real models, not
  an approximation.
- `alembic downgrade base` cleanly removes everything.
- `alembic stamp head` against a database that already has the tables
  (mirroring Sarah's real Neon state) correctly marks it current with
  **zero DDL executed** — confirmed by inspecting the DB directly
  before/after, only the new `alembic_version` bookkeeping table appears.

**What Sarah needs to do, once, before anything else in this slice
applies to her real database:** `pip install alembic` (added to
`requirements.txt`), then from `pawgress-backend/` with her real
`DATABASE_URL` set: `alembic stamp head`. This is a one-time, no-op
bookkeeping step — it does not touch any existing table or data.

### Slice B — Full Goal Hierarchy (Blueprint §13)

**Domain model** (`productivity/models.py`): `Goal` gains `tier` (new
`GoalTier` enum: `Annual | Quarterly | Project | Milestone`, **nullable**)
and `parent_goal_id` (nullable, self-referential FK, **no DB-level
cascade** — same reasoning as ADR 0001's Task→Goal decision: unlinking
lives in one deliberate application-code function, not implicit DDL).

**Key design decision, not explicitly specified in the docs, made and
recorded here:** `tier` is optional. A Goal with `tier = null` behaves
exactly like the original flat MVP goal — no forced migration of existing
data's meaning, no assumption imposed on goals a user never asked to be
part of a hierarchy. Assigning a tier is how a user opts into hierarchy at
all, which is a direct, literal reading of Domain Model §4.3's "the system
earns hierarchy, it doesn't assume it" — enforced at the schema level, not
just in the UI, since `parent_goal_id` can only be set when *both* the
goal and its proposed parent already have a tier.

**Invariant enforced** (`productivity/goal_service.py`): a parent must be
a *strictly broader* tier than its child (Annual > Quarterly > Project >
Milestone by rank). This single rule also makes cycles structurally
impossible — no separate ancestor-walk needed, since rank can only ever
strictly decrease moving down a chain. Any tier is a legal parent as long
as it's strictly broader — a Milestone can attach directly to an Annual
goal with no Quarterly/Project in between; hierarchy isn't forced to be
fully populated.

**Deletion** (`delete_goal_and_unlink_references`, renamed from
`delete_goal_and_unlink_tasks`): extends Domain Model Invariant 9 to the
new relationship — deleting a Goal unlinks both referencing Tasks *and*
child Goals in the same transaction, never cascading deletes to either.

**Real correctness bug caught and fixed before shipping:** changing a
goal's `tier` alone (without touching `parentGoalId` in the same request)
could silently leave the tree in an invalid state if the goal already had
an existing parent or child edge that the new tier would violate — e.g. a
Milestone re-tiered to Annual while still parented under another Annual
goal. Fixed by re-validating every existing edge a goal participates in
whenever its tier changes, rejecting the whole request (422, nothing
persisted) rather than silently corrupting the tree or silently unlinking
something the user didn't ask to unlink. Covered by three dedicated tests
in `test_goal_hierarchy.py`.

**API** (`productivity/routes.py`): `POST /goals` gains an optional
`tier` (no `parentGoalId` accepted at creation — assigning a parent is a
deliberate follow-up action, mirroring why manual task creation doesn't
accept `goalId` either, UX Philosophy §5.4). New `PATCH /goals/{id}`
(didn't exist before) — same one-tap-correction shape as `PATCH
/tasks/{id}`: any of `label`/`tier`/`parentGoalId`, one field or several,
no confirmation. `parentGoalId: null` explicitly clears a link.

**Frontend** (`features/goals/`): `goalHierarchy.ts` (pure tree-building +
eligible-parent helpers, mirrors the backend's tier-ordering exactly so
the UI can pre-filter without a round trip, though the server still
re-validates regardless), `GoalNode.tsx` (recursive tree row: tier badge,
inline tier-change select, parent picker reusing the same UI pattern
already used for Task→Goal linking, delete with the existing undo-toast).
`GoalsPage.tsx` rewritten: goals with no tier render exactly as the old
flat list did (now with an added "Add to hierarchy..." select so an
*existing* flat goal can still gain a tier later, not just new ones);
tiered goals render as a nested tree below.

**Testing:**
- 20 new backend tests in `tests/test_goal_hierarchy.py` (tier assignment,
  valid/invalid parent linking, cross-user isolation, the tier-change
  re-validation edge case in both directions, deletion unlinking). Full
  suite: **53/53 passing** (33 original + 20 new), against the existing
  SQLite-based test harness.
- Additionally verified live, end-to-end, against a real running
  `uvicorn` server backed by real PostgreSQL 16 (not just the SQLite test
  double) — register → create Annual + Project goals → link → confirm
  reversed-tier-order link correctly rejected (422) → confirm flat goal
  stays flat → delete the Annual parent → confirm the Project child
  survives, unlinked, not deleted. All behaved exactly as designed.
- `tsc -b` clean, `vite build` clean (109 modules, no errors).
- **No frontend automated tests** — same known gap as the companion
  slice; no Vitest/Jest tooling exists in this repo yet.

---

## Just Completed: V2 Journal (Slice C, 2026-08-18)

New, fully standalone module (`journal/`) — deliberately NOT built as an
extension of the AI Inbox. Per Domain Model §13: "journaling and
task-extraction are different intents even though both start as natural
language." That separation is structural here, not just naming: verified
by a dedicated test (`test_journal_module_has_no_ai_extraction_dependency`)
that AST-parses `journal/routes.py` and asserts it never imports
`ai_extraction` — a future edit can't silently wire extraction into this
surface without that test catching it.

**Domain model** (`journal/models.py`): `JournalEntry` — `id`, `user_id`,
`text`, `created_at`, `updated_at`. No relation to Capture, Task, or Goal.

**Judgment calls made and recorded, not asked about:**
- **No title field** — a forced structure the docs never asked for.
- **Entries are editable** (unlike Capture's immutable raw text). Capture's
  immutability protects extraction provenance (Domain Model Invariant 4);
  there's no extraction here to protect, and refining a reflection (typo,
  add a line) is closer to editing a Task title than to Capture's
  audit-trail-like permanence. One-line reversible if this turns out wrong
  (drop the PATCH endpoint).
- **No companion tie-in, no streak/frequency signal anywhere** — the
  anti-shame, no-absence-signal philosophy (FR-6.2, Blueprint §5) is
  written specifically about the companion, but the same reasoning was
  applied here by extension: nothing on this page ever mentions how long
  it's been since the last entry, and the cat has no reaction wired to it.

**API**: `POST /journal`, `GET /journal` (newest first), `PATCH
/journal/{id}`, `DELETE /journal/{id}` (permanent, no confirmation — same
reasoning as AC-3.5.1). All scoped to the authenticated user.

**Frontend** (`features/journal/JournalPage.tsx`): a write-and-save form
at the top (visually consistent with the AI Inbox's capture form, since
both are "write freely" surfaces — though nothing here goes through
extraction), entries listed below with explicit Edit/Save/Cancel (not
auto-save-on-blur — a deliberate choice for longer, more personal text,
where an accidental blur mid-selection shouldn't silently commit a change)
and the same instant-delete-plus-undo pattern used everywhere else in the
app. New `/journal` route and nav link in `AppShell`.

**Migration**: `6889870f5bf3_add_journal_entries.py` — clean autogenerate,
no fix-ups needed this time (no enum types, no self-referential FK, unlike
the goal hierarchy migration). Verified with the same full up/down/up
round-trip against real PostgreSQL 16, plus a confirmed-empty second
autogenerate diff.

**Testing:**
- 11 new backend tests in `tests/test_journal.py` (CRUD, cross-user
  isolation, the AST-based extraction-independence guard). Full suite:
  **64/64 passing** (53 prior + 11 new).
- Verified live, end-to-end, against a real running `uvicorn` server
  backed by real PostgreSQL 16 — create → edit (confirmed `updatedAt`
  bumps while `createdAt` stays fixed) → list → delete. All correct.
- `tsc -b` clean, `vite build` clean (110 modules).
- No frontend automated tests — same known, named gap as every prior
  slice; still no Vitest/Jest tooling in this repo.

---

## Just Completed: V2 Habits (Slice D, 2026-08-19)

The one V2 piece the docs explicitly warned against building naively —
Blueprint §16 names traditional streak psychology directly as "proven
precisely because it works through mild guilt, which this product has
explicitly ruled out." Sarah delegated the concrete design calls (asked,
via three targeted questions, then said proceed) rather than making them
herself; recording exactly what was decided and why, since this feature
had no existing precedent in the codebase to extend.

**Three governing decisions, made explicitly:**
1. **No streak counter at all.** Progress is a plain accumulating total
   that never resets — the same principle already locked in for the
   companion's future growth model (`companion-character-spec.md` §5.E:
   "growth reflects accumulated progress, never daily performance...
   never reversible by missed days"), applied here to Habits. There is no
   "current streak" field anywhere in the schema, and no code path
   computes one.
2. **Scheduling is per-habit**, not one forced shape — Daily or a
   flexible "X times a week" — same "don't force rigidity" reasoning
   already established for Category staying free text (Domain Model §6).
3. **Missed days are never recorded, anywhere, not even internally.**
   `habits/models.py` only knows how to store positive completion events.
   There is no "missed" row, no absence flag, no computed gap — this is
   "silence is a valid design choice" (Blueprint §4) enforced at the
   schema level, not just suppressed at the display level.

**Domain model** (`habits/models.py`): `Habit` (label, `frequency` enum
`Daily`/`WeeklyCount`, optional `weeklyTarget`, optional `goalId` — same
pattern as Task→Goal, no DB cascade) + `HabitCompletion` (habit_id, date,
unique per habit+day — binary per day, same exactly-two-states precedent
as Task's own status field, just applied to a calendar day instead of a
task). **One deliberate, narrow exception to this codebase's "unlink,
never cascade" rule:** deleting a Habit *does* cascade-delete its
completions at the DB level (`ON DELETE CASCADE`) — recorded explicitly
in the model's docstring as to why this is different from every other
relationship here: a completion has no meaning independent of its habit,
unlike Task/Goal (which must both remain independently meaningful) or
Capture (retained forever as future-memory seed data). There's no
retention rationale for orphaned completions.

**Real infrastructure gap found and fixed while building this:** SQLite
(used by the test harness) does not enforce foreign key constraints,
including `ON DELETE CASCADE`, unless explicitly told to per-connection —
Postgres (the real database) does this automatically. Without fixing
this, the cascade-delete test could have passed or failed for the wrong
reason, never actually exercising real referential-integrity behavior.
Fixed with a process-wide SQLAlchemy event listener in
`shared/database.py` (dialect-checked, zero effect on Postgres) — applies
to every SQLite connection created anywhere in the process, including the
test harness's own separately-constructed engine.

**Two migration bugs of the same class as the goal hierarchy migration**,
caught and fixed the same way: Postgres ENUM types (`habitfrequency`) are
correctly created by `CREATE TABLE`, but never automatically dropped by
`DROP TABLE` on downgrade — verified directly (found an orphaned type via
`\dT` after a raw downgrade), fixed by explicitly dropping the enum type
at the end of `downgrade()`.

**API** (`habits/routes.py`): full CRUD, plus `POST
/habits/{id}/completions` (idempotent — marking an already-complete day
again is a harmless no-op, not an error) and `DELETE
/habits/{id}/completions/{date}` (undoes a completion; does not create a
"missed" record — there's no such thing to create). Update consistency
follows the exact same discipline already established for Goal hierarchy:
changing `frequency` alone in a way that would leave an existing
`weeklyTarget` inconsistent is rejected outright (422), never silently
auto-corrected.

**Frontend** (`features/habits/HabitsPage.tsx`): create form (label,
frequency, conditional weekly-target field, optional goal link), a list
of habit rows each with a plain circular toggle (fills with the
assistant's teal only on direct tap — no ambient "you haven't done this"
color signal, which would itself be a loss-framed visual element per
Blueprint §14), the accumulating count shown as plain body text ("done 12
times"), inline label editing via a small `HabitRow` sub-component
(matches `TaskRow.tsx`'s exact always-editable-input pattern rather than
inventing a new edit-toggle convention), and the same undo-toast delete
pattern used everywhere else. New `/habits` route and nav link.

**Testing:**
- 16 new backend tests in `tests/test_habits.py` — frequency/target
  consistency (creation and partial-update), idempotent completion
  marking, the cascade-delete behavior (verified directly against the DB,
  not just via the API), cross-user isolation, goal linking. Full suite:
  **80/80 passing** (64 prior + 16 new), in a genuinely clean-room `venv`
  install from `requirements.txt`.
- Migration verified with the same full up/down/up round-trip against
  real PostgreSQL 16, including a manual check that the enum type is
  actually gone after downgrade (not just assumed).
- Verified live, end-to-end, against a real running `uvicorn` server
  backed by real PostgreSQL 16 — create → mark complete (twice, confirming
  idempotency) → reject invalid `WeeklyCount` without a target → list →
  delete. All correct.
- `tsc -b` clean, `vite build` clean (111 modules).
- No frontend automated tests — same known, named gap as every prior
  slice.

---

## Just Completed: V2 Calendar (Slice E, 2026-08-20) — read-only v1

Sarah made the scope calls for this one explicitly and in writing before
any code was touched (unlike Slices B–D, which ran under standing
authorization to just build and flag anything critical). Recording
exactly what was decided, since this slice is genuinely different in
kind from everything before it — it's the first one involving an
external, third-party service.

**Explicit scope (Sarah's decisions, not Claude's):**
- **Calendar is a completely separate surface.** `Task` was not touched —
  no `due_date`, no `scheduled_at`, no calendar identifiers. Domain Model
  §4.2's deliberate exclusion of scheduling from Task stays fully intact.
  Daily View was not reinterpreted as a calendar.
- **Google Calendar only**, v1. No generalized multi-provider system.
- **Read-only: Google → Pawgress.** No writes, no event creation/editing/
  deletion on Google's side, no two-way sync, no task-from-event
  automation.
- **Calendar data never reaches Groq, ever** — not for categorization,
  not for summaries, not silently added to any existing AI call. Verified
  structurally (see Testing below), not just by review discipline.
- **UI stays calm.** No productivity scores, no task/goal/habit overlays,
  no AI summaries, no companion reactions, no analytics, no gamification.
  Just "what's already happening in my life," grouped by day.

**Architecture, inspected against the real repo before building** (per
Sarah's explicit instruction, point 7): confirmed Domain Model's
Task/scheduling exclusion is unchanged, confirmed the existing
provider-abstraction pattern (`ai_extraction/provider.py`) to mirror,
confirmed the existing test-stubbing convention (`test_task_deletion.py`'s
`StubProvider`), confirmed env-var handling (`shared/config.py`), and
confirmed frontend routing conventions — before writing any code, exactly
as instructed.

**New isolated module** (`calendar_integration/` — deliberately not named
`calendar`, which would silently shadow Python's own standard-library
`calendar` module): `models.py`, `schemas.py`, `google_provider.py`,
`routes.py`. One new table, `calendar_connections` (one per user —
`user_id` is unique; connecting again replaces the existing connection,
no multi-account support in v1).

**One real design correction made while building, not after:** the first
draft of the OAuth `state` parameter (needed because Google's redirect
hits the backend directly, without this app's own Bearer token) used an
in-memory server-side map from `state` to user id. Caught before writing
further code: an in-memory map would silently break the moment this app
ever runs behind more than one worker process, directly violating System
Architecture §22's explicit "stateless replicas, no session state in
server memory" constraint. Fixed by making `state` itself a short-lived,
signed token (same secret/mechanism as session tokens, `identity/auth.py`)
carrying the user id and a distinct `"purpose"` claim — no server-side
storage needed at all, and the purpose claim stops a normal session token
from being usable as an OAuth state token or vice versa.

**Security decision, made explicitly by Sarah before building, not
assumed:** the stored Google refresh token relies on this codebase's
existing DB-level encryption-at-rest baseline (System Architecture §17)
rather than a new application-level encryption layer with its own
key-management story. Flagged as a real tradeoff before building (nothing
else in this schema is a live, standing account credential the way a
refresh token is); Sarah gave the explicit green light to the proposed
default.

**Provider approach:** plain HTTP via `httpx` for both the OAuth token
exchange and the Calendar API v3 `events.list` call, rather than Google's
official `google-api-python-client`/`google-auth-oauthlib` stack —
matches the existing thin-REST-wrapper pattern already used for Groq
(`ai_extraction/provider.py`), avoiding a much heavier dependency chain
for what's really two REST calls. Scope requested:
`calendar.events.readonly` — narrower than the more commonly-used
`calendar.readonly`, since this feature never needs calendar list/settings
visibility, only event data.

**Real infrastructure bug found and fixed while building, worth knowing
about beyond just this slice:** confirmed directly (via a standalone
diagnostic script, not assumed) that **SQLite silently strips timezone
awareness from a `DateTime(timezone=True)` column on round-trip through
SQLAlchemy**, while real PostgreSQL preserves it correctly. Comparing a
naive and a timezone-aware datetime in Python raises `TypeError` — which,
in the original code, was being silently caught by a broad exception
handler and surfaced as a generic "couldn't reach Google" error, masking
a real bug behind a plausible-looking one. Fixed by normalizing a naive
`access_token_expires_at` to UTC before comparing
(`calendar_integration/routes.py::_get_valid_access_token`). **Worth
flagging as a class of bug**, not just a one-off: anywhere else in this
codebase that ever compares a DB-read datetime directly in Python (rather
than inside a SQL `.filter()` clause, which SQLAlchemy handles
differently) could have the same latent issue on SQLite specifically —
this was caught here because a test happened to exercise it, not because
of a systematic audit.

**API:** `GET /calendar/status`, `GET /calendar/oauth/start`, `GET
/calendar/oauth/callback` (hit directly by Google's redirect, not an
authenticated API call), `GET /calendar/events`, `DELETE
/calendar/connection`. A Google API/refresh failure (e.g. the user
revoked access from their Google account settings) surfaces as a plain
502 asking the user to reconnect — the stored connection is deliberately
left in place rather than silently deleted, so `/status` still shows
"connected" until the user takes an explicit action.

**Frontend** (`features/calendar/CalendarPage.tsx`): not-connected state
shows a plain explanation and a connect button; connected state shows
"Connected as [email]" + Disconnect, and an agenda-style list of events
grouped by day (deliberately not a grid/month view — calmer, and matches
"what's happening" framing better than a dashboard). Handles the
post-OAuth redirect back from Google (`?connected=1`) by quietly
refetching status and clearing the query param — no banner, no
celebratory copy. New `/calendar` route and nav link.

**Environment variables added:** `GOOGLE_CLIENT_ID`,
`GOOGLE_CLIENT_SECRET`, `GOOGLE_OAUTH_REDIRECT_URI` — all **optional**,
deliberately NOT added to `Settings.validate()`'s required-at-startup
check, since Calendar is opt-in and a user who never touches it shouldn't
be blocked from running the rest of the app. A route that actually needs
them fails clearly (503, not a crash) if they're missing — verified live
against a real running server with real Postgres and no Google
credentials set, specifically to confirm this exact path.

**Testing:**
- 24 new backend tests in `tests/test_calendar.py` — full OAuth-state
  lifecycle (valid, invalid, expired, wrong-purpose), connect/reconnect,
  event listing and normalization, the access-token silent-refresh path
  (including the SQLite datetime bug above, caught by this exact test),
  disconnect (including the graceful no-op case), cross-user isolation,
  and two structural AST-based guards confirming `calendar_integration/`
  never imports `ai_extraction` **or** `productivity`/`habits` — the
  "calendar data never reaches AI" and "Calendar never touches Task"
  boundaries are enforced by a test, not just code review discipline.
  Full suite: **98/98 passing** (80 prior + 18 new), verified in a
  genuinely clean-room `venv` install.
- Migration verified with the same full up/down/up round-trip against
  real PostgreSQL 16 — clean this time, no enum-type fix-up needed (no
  enums in this table).
- Verified live against a real running `uvicorn` server backed by real
  PostgreSQL 16: auth protection, `/calendar/status` when not connected,
  the "not configured" 503 path with no Google credentials set, 404 on
  `/calendar/events` with no connection, graceful 204 on disconnecting
  nothing. **What could NOT be verified from this environment, stated
  plainly rather than glossed over:** the real, live OAuth consent-screen
  handshake against Google's actual servers — no network path to
  `accounts.google.com` exists in this sandbox. See the manual
  verification steps at the top of this file.
- `tsc -b` clean, `vite build` clean (112 modules).
- No frontend automated tests — same known, named gap as every prior
  slice.

---

## V2 Roadmap (current priority order, per Sarah 2026-08-15)

| # | Piece | Status |
|---|---|---|
| 1 | Alembic baseline (Slice A) | ✅ **Done** — see below |
| 2 | Full goal hierarchy (Slice B) | ✅ **Done** — see below |
| 3 | Journal (Slice C) | ✅ **Done** — see below |
| 4 | Habits (Slice D) | ✅ **Done** — see below |
| 5 | Calendar integration (Slice E) | ✅ **Done, read-only v1** — see below. Real live testing blocked on Sarah's manual Google Cloud Console setup (see top of this file). |
| 6 | Weekly Reviews / pattern detection / AI Coach | ⬜ **Not honestly buildable yet** — needs real usage history that doesn't exist yet |

**Still deferred, unchanged from before:** companion placement change
(header → near/on top of task list), remaining Polish Sprint items.

**Deferred to after V2 substance** (Sarah's explicit call, 2026-08-15):
- Companion placement change (header → near/on top of the task list) — see
  the open design idea logged under Companion Character below.
- Remaining Polish Sprint items (empty states' last piece, onboarding,
  visual consistency, mobile responsiveness) — paused, not abandoned.

---

## Polish Sprint Roadmap (paused 2026-08-16 — resumes after V2 substance)

| # | Slice | Status |
|---|---|---|
| 1 | Empty states designed around the companion | 🟡 Mostly done — task list + goals shipped; "cat waiting beside input" (First Capture) treatment approved but not yet built, and now a natural candidate for re-skinning onto `CompanionCharacter` |
| 2 | Companion presence refinement | ✅ Done (2026-08-15) |
| 3 | Onboarding through design, not tutorials | ⬜ Not started — only if genuinely needed |
| 4 | Keyboard and accessibility improvements | 🟢 Partially done (Slice 1 of this sprint) |
| 5 | Visual consistency pass | ⬜ Not started |
| 6 | Mobile responsiveness review | ⬜ Not started |
| 7 | Final infrastructure pass | ✅ Alembic baseline done (as Slice A above, pulled forward early since the goal hierarchy needed it); remaining cleanup still open |

---

## Companion Presence Refinement (done 2026-08-15)

Built `CompanionCharacter` + `useCompanionBehavior` against the real,
confirmed-final production assets, per `docs/companion-character-spec.md`,
and wired them into `AppShell`'s header, fully replacing the placeholder
paw-glyph `CompanionIndicator`.

**What was built** (`pawgress-frontend/src/features/companion/`):
- `companionConfig.ts` — `CompanionExpressionKey` (abstract key, never an
  asset import outside this module), the asset map for all 7 production
  PNGs, and every tunable number (expression weights per mood, reaction
  weights, all timing) isolated in one place, explicitly marked
  PROVISIONAL — not a locked product decision, retune freely.
- `useCompanionBehavior.ts` — implements Layer B (weighted random
  expression selection, rerolls on mood change + its own slower cadence),
  Layer C (mood-independent ambient whole-image transform: stretch or
  wobble, skipped entirely under `prefers-reduced-motion`, not just
  CSS-overridden), and Layer D (`reactToCapture()`, a brief alert-biased
  reaction that reverts on its own). `triggerEarnedDelight()` is exposed
  as a reserved stub only — intentionally not implemented, per the spec:
  the real trigger condition needs status-history tracking that doesn't
  exist in the domain model yet.
- `CompanionCharacter.tsx` — fetches mood via the existing
  `GET /companion/state` query (unchanged backend/API), renders a
  two-layer `<img>` crossfade between expression images (a flattened PNG
  swap can't crossfade via a single `background-image` transition),
  exposes `reactToCapture` via `forwardRef`/`useImperativeHandle`. Renders
  nothing until mood has loaded — no spinner for a peripheral element.
- `CompanionReactionContext.tsx` — small bridge so `CapturePage` (a routed
  descendant, not a direct child of `AppShell`) can call the header
  companion's `reactToCapture()` without prop-drilling through routing.

**Wiring:**
- `AppShell.tsx` now renders `CompanionCharacter` instead of
  `CompanionIndicator`, holds the ref, and wraps its children in
  `CompanionReactionProvider`.
- `CapturePage.tsx` calls `reactToCapture()` in the capture success
  handler — fires on every successful capture, including zero-task ones,
  since a purely reflective capture is still a genuine moment of being
  heard.
- `CompanionIndicator.tsx` deleted — fully superseded, no remaining
  references (confirmed via grep across `src/`).
- `index.css` — old `.companion-indicator`/`.companion-glyph` rules
  replaced with `.companion-character` + crossfade/ambient-transform
  rules; added `--duration-companion-crossfade` token (kept in sync with
  `COMPANION_TIMING.crossfadeMs` — noted in both places).

**v1 scope respected exactly:** flattened whole-image PNGs only, no
layering/reconstruction attempted; no blink/gaze/ear/tail sub-part
animation (needs separated layers this format doesn't have); no new
backend, API, or domain-model changes; no absence-duration signal
anywhere in the new code (confirmed by construction — nothing in
`useCompanionBehavior` reads elapsed time, only schedules its own future
timers).

**Verified:** `tsc -b` clean, `vite build` clean (106 modules, no errors).

**Not done as part of this slice, flagged rather than silently skipped:**
- **No automated tests** — this repo has no frontend test tooling
  (Vitest/Jest) set up yet, so there was nothing to plug hook/component
  tests into without introducing a new toolchain, which wasn't part of
  what was approved for this slice. Worth a explicit decision on whether
  to add frontend test infrastructure in a future slice.
- **Asset file size** — the 7 PNGs are 820KB–1.18MB each (~6.6MB total,
  uncompressed, per `vite build`'s output) for what's currently only used
  at a ~30px header scale. Not touched in this slice (modifying the
  production art itself wasn't in scope, and compressing/resizing is a
  real content decision, not just a technical one) — flagging for a
  deliberate call before this ships anywhere real, especially once the
  same assets get reused at larger scale (e.g. the First Capture empty
  state).

---

## Companion Character — Design Locked, Now Partially Implemented

**Full locked specification: `docs/companion-character-spec.md`** — now
also committed to the repo (was previously only available as an attached
project file, not in-repo; fixed this slice since other docs, including
this one, reference it as if it's already there).

- **v1 scope locked:** 1 character, 2 poses (Idle/Sitting, Sleeping),
  6 expressions (Calm, Curious, Affectionate, Sleepy, Playful, Mischievous)
- **Backend mood unchanged:** still exactly Neutral/Content/Attentive, no
  new enum values, no new persisted fields
- **Behavior model:** 4 layers — now implemented in
  `useCompanionBehavior.ts` exactly as designed. Growth stage (Layer E) is
  still reserved, not built.
- **Confirmed excluded, explicitly, not just deferred:** any behavior tied
  to return-after-absence, any feeding mechanic, any virtual-pet mechanic,
  any gamification. Verified in this slice's implementation: nothing in
  the new code computes or reads elapsed time since last activity.
- **Asset format:** flattened whole-image transparent PNGs (v1), locked
  2026-08-09. `CompanionExpressionKey` stays an abstract key so a future
  true-layered renderer is a swap, not a rewrite.

**Remaining follow-up work, not yet scheduled:**
- Re-skin the "cat waiting beside input" First Capture empty state (item 1)
  onto `CompanionCharacter` — natural next slice, not bundled into this one.
- Re-skin the task-list/goals empty-state glyphs onto real art, if desired
  (currently still the glyph-level `EmptyState` component — untouched this
  slice, still fully functional as-is).
- Decide on the asset file-size question above before any larger-scale use.
- **Open design idea (Sarah, 2026-08-15, not decided, not built):** Sarah
  would prefer the companion live near/on top of the task list rather than
  in the header. Real tension worth surfacing before building toward it:
  current placement was a deliberate choice matching Brand §10's restraint
  principle ("small, easy to miss if you're not looking... peripheral by
  design"), and BR-3 strictly bans the cat as primary visual focus during
  the First Capture moment specifically — but the ordinary task-list view
  isn't under that same rule, so there's more room there than in capture.
  Needs its own design proposal + explicit sign-off before building, not a
  quiet reinterpretation of the current header placement.

---

## Done — Full Foundation (pre-Polish-Sprint)

- Auth, First Capture + extraction, one-tap correction, manual task
  creation, goals + linking, task deletion, minimal Cat Companion
- FR-1.3 profile default (`GET /auth/me`, minimal Account page)
- AI cost/latency logging (structured logs, ADR 0003)
- Three ADRs (0001 goal-deletion/hardening, 0002 companion mood, 0003 cost logging)
- 33 backend tests passing (verified count directly against the cloned repo)

## Done — Polish Sprint Slice 1 (motion/a11y/undo/companion/keyboard)

- Motion/timing token system (`--duration-quick/settle/ambient`, `--ease-quiet`)
- Real WCAG AA contrast audit — found and fixed genuine failures (original
  `text-muted` measured 3.34:1, `cat` brass measured 2.32:1; both corrected
  with computed, not eyeballed, ratios), plus skip-link, landmark, and
  ARIA-label additions
- Undo-toast on delete, tasks and goals both (replaces no-feedback delete,
  does not reintroduce a confirmation dialog — AC-3.5.1 stays intact)
- Cmd/Ctrl+Enter capture shortcut; post-capture auto-scroll+focus to the
  first newly created task
- Goal-delete visual consistency with task-delete
- (Companion idle breathing/stretch from this slice has since been
  superseded by the real `CompanionCharacter` above — the glyph-level
  implementation and its CSS no longer exist.)

## Done — V2 Slices A–E (2026-08-16 through 2026-08-20)

- Alembic baseline, full goal hierarchy, Journal, Habits, Calendar
  (read-only v1) — see full write-ups near the top of this file for each.
  **98 backend tests passing** (33 MVP-era + 20 hierarchy + 11 journal +
  16 habits + 18 calendar), verified against both the SQLite test
  harness and, for each slice, a real, live, running Postgres-backed
  server. Calendar's real live Google OAuth handshake still needs
  Sarah's one-time manual verification locally — see the top of this
  file.

## Known, deliberate gaps (not oversights)

- **First-capture helper text** — explicitly on hold, revisit after living
  with the interface longer. The narrower "cat waiting" presence-only
  version is a *separate* question, still awaiting a build slice (see
  Companion Character section above) — don't conflate the two if
  revisiting either.
- **Status-history tracking for earned-delight triggers** (e.g. "task
  circled back to multiple times") — flagged repeatedly as a real Domain
  Model gap; `useCompanionBehavior.triggerEarnedDelight()` reserves the
  interface slot but does not implement it, exactly as the spec directs.
- **Frontend test tooling now exists** (Vitest + Testing Library, added
  2026-08-22) — but coverage is still narrow: only `goalHierarchy.ts` and
  `useCompanionBehavior.ts` have real tests. No page-level component
  (`CapturePage`, `GoalsPage`, `JournalPage`, `HabitsPage`,
  `CalendarPage`, `AppShell`) has any test coverage yet, and neither does
  `CompanionCharacter`'s actual rendering. The infrastructure gap is
  closed; the coverage gap is real and worth naming honestly rather than
  implying more is tested than actually is.
- **Sarah is deferring `alembic stamp` + `upgrade` until the end of the
  project** (her explicit call, 2026-08-19) — safe to do, since nothing in
  this process ever touches her real Neon database automatically. When
  she's ready, it's **two commands, not one** (corrected from an earlier,
  incomplete note in this file):
  ```
  alembic stamp a6bf4696c8da   # marks her existing pre-hierarchy tables as baseline
  alembic upgrade head          # actually applies goal-hierarchy + journal + habits (and anything landed by then)
  ```
  Until she runs both, her real database still has the original 5-table
  MVP schema — none of the goal-hierarchy, journal, or habits features
  will work against it yet. This is expected and fine to leave as-is for
  as long as she wants; it only matters at the moment she tries to
  actually run the merged app for real. (Now also covers the Calendar
  migration — same two-command sequence, just further ahead in the chain
  by the time she runs it.)
- **SQLite silently strips timezone-awareness from `DateTime(timezone=True)`
  columns** on round-trip through SQLAlchemy, confirmed directly via a
  standalone diagnostic during the Calendar slice — real PostgreSQL does
  not have this problem. Fixed at the one call site that hit it
  (`calendar_integration/routes.py`), but flagged here as a **class of
  bug**, not a one-off: any future code that compares a DB-read datetime
  directly in Python (as opposed to inside a SQL `.filter()` clause,
  which SQLAlchemy handles differently) should normalize to
  timezone-aware first, or it will work fine against real Postgres and
  silently misbehave only in the SQLite-backed test suite — worth a
  quick grep across the codebase next time datetime comparisons are
  touched, not necessarily an urgent audit now.
- **Calendar's real, live Google OAuth handshake has not been tested
  end-to-end** — see the manual verification steps at the top of this
  file. Everything else about the slice is verified; this one piece
  structurally cannot be, from this environment.

---

## How to use this file

- Read this before doing anything else in a new session — it's faster and
  more reliable than re-deriving state from chat history or memory.
- Update it at the end of every slice: move the row from "in progress" to
  "done," add anything newly discovered, note anything left deliberately
  unresolved.
- If this file and Claude's memory of past conversations disagree, this
  file wins — it's versioned in the repo, memory is not.
