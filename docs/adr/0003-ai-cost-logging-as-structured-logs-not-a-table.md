# ADR 0003: AI cost/latency tracking implemented as structured logs, not a database table

**Status:** Accepted
**Date:** 2026-08-06
**Context:** System Architecture §19 requirement — "AI cost/performance
metrics (tokens used, latency per provider call, model tier used) —
tracked per-request from day one... this needs to exist before it's
urgent, not after." This is an explicit, already-approved requirement;
this ADR documents the *mechanism* chosen to satisfy it, which the
documents themselves leave open.

---

## Decision

`ai_extraction/provider.py` now records `model`, `outcome`, `latency_ms`,
`input_tokens`, `output_tokens`, and `attempt` for every extraction call
(success, schema-invalid, and provider-error paths alike) and emits one
structured JSON line per call via a dedicated logger
(`ai_extraction/cost_logger.py`, logger name `pawgress.ai_cost`). No new
database table, no new domain entity.

## Why a log line, not a table

System Architecture §19 requires these metrics to be *tracked*
per-request. It does not require them to be *queryable through the
product* — there's no in-app cost dashboard in MVP scope (Domain Model
§13 doesn't name one), and Business Model §5's cost concern is about
Sarah having the numbers to look at, not end users seeing anything.

A database table would add real, currently-unjustified scope: a
migration, a new row of BR-10's deletion-guarantee obligation if the
table were ever linked to a user id, and a retention-policy question this
document set has no opinion on yet. None of that is required by "tracked
per-request" as written. A structured log line is the smallest correct
implementation of the actual requirement, consistent with System
Architecture §1's governing constraint (build the smallest thing that's
honestly correct for what's approved now).

**Deliberately not user-linked.** The log record has no `user_id` and no
Capture/Task reference — only `model`, `outcome`, `latency_ms`, token
counts, and `attempt`. This keeps the record entirely outside BR-10's
scope (there's no per-user data to delete) and outside §17's raw-content
rule (there's nothing here that could leak Capture text or Task titles,
structurally — the function signature has no parameter that could carry
either).

## What this doesn't do (yet)

There's no aggregation, no cost-per-user rollup, no alerting. Right now
this satisfies "the number exists in a log line, from day one" — actually
using it (e.g., computing `cost_model.md`'s formulas against real traffic)
is a manual `grep`/`jq` pass against stdout for now, which is adequate at
current traffic and consistent with "don't build ahead of measured need."

## Revisit if

- Sarah wants a queryable cost view inside the product (a real dashboard,
  not a grep) — at that point this is worth promoting to a table or a
  proper log-shipping pipeline. The log schema (flat, named fields) was
  chosen specifically so that promotion is a mechanical change, not a
  redesign.
- Real deployment moves logs somewhere that isn't easily greppable
  (e.g., a managed platform that doesn't surface stdout) — at that point
  `cost_logger.py` needs a real sink, not `logging.basicConfig`'s
  stdout default (`main.py`).
