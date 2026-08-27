/**
 * features/companion/companionConfig.ts
 *
 * v1 asset reality (docs/companion-character-spec.md §6, §3): 7 flattened,
 * whole-image transparent PNGs — 6 Idle expressions + 1 Sleeping pose. No
 * separated layers exist yet, so there is no pose × expression matrix to
 * manage, just 7 discrete images to pick between. `CompanionExpressionKey`
 * stays an abstract key (never an asset import) specifically so a future
 * true-layered renderer is a swap behind this module, not a rewrite of
 * anything that consumes it.
 *
 * TUNING: every number below is a provisional default, not a locked product
 * decision (explicitly confirmed — see conversation). Nothing else in this
 * feature depends on the exact percentages or millisecond values; retune
 * freely once the real behavior has been seen in the UI.
 */

import type { CatMoodState } from "../../shared/types";

import idleCalm from "../../assets/companion/idle-calm.png";
import idleCurious from "../../assets/companion/idle-curious.png";
import idleAffectionate from "../../assets/companion/idle-affectionate.png";
import idleSleepy from "../../assets/companion/idle-sleepy.png";
import idlePlayful from "../../assets/companion/idle-playful.png";
import idleMischievous from "../../assets/companion/idle-mischievous.png";
import sleepingAsset from "../../assets/companion/sleeping.png";

export type CompanionExpressionKey =
  | "calm"
  | "curious"
  | "affectionate"
  | "sleepy"
  | "playful"
  | "mischievous"
  | "sleeping";

export const COMPANION_EXPRESSION_ASSETS: Record<CompanionExpressionKey, string> = {
  calm: idleCalm,
  curious: idleCurious,
  affectionate: idleAffectionate,
  sleepy: idleSleepy,
  playful: idlePlayful,
  mischievous: idleMischievous,
  sleeping: sleepingAsset,
};

/**
 * Layer B (useCompanionBehavior) — weighted, not a lookup table. Mood shifts
 * probability, it never excludes an option outright, per
 * companion-character-spec.md §5.B. `sleeping` is deliberately present ONLY
 * under Neutral, and only as an ordinary low-probability personality trait —
 * it must never be reachable from Attentive/Content, and nothing in this
 * table (or anywhere else in the companion feature) is a function of how
 * long it's been since the user was last active. There is no
 * absence-duration signal anywhere in this system.
 *
 * PROVISIONAL — see module docstring.
 */
export const COMPANION_EXPRESSION_WEIGHTS: Record<
  CatMoodState,
  Partial<Record<CompanionExpressionKey, number>>
> = {
  Neutral: { calm: 35, curious: 10, affectionate: 5, sleepy: 25, playful: 5, mischievous: 15, sleeping: 5 },
  Attentive: { calm: 20, curious: 45, affectionate: 5, sleepy: 5, playful: 15, mischievous: 10 },
  Content: { calm: 15, curious: 5, affectionate: 40, sleepy: 5, playful: 30, mischievous: 5 },
};

/**
 * Layer D (reactToCapture) — a brief, restrained bias toward alertness.
 * Deliberately a small subset of expressions, not the full mood table.
 * PROVISIONAL.
 */
export const COMPANION_REACTION_WEIGHTS: Partial<Record<CompanionExpressionKey, number>> = {
  curious: 65,
  playful: 35,
};

/** All timing knobs in one place. PROVISIONAL. */
export const COMPANION_TIMING = {
  /** Layer B: how often the expression rerolls on its own, independent of mood changes. */
  expressionRerollMinMs: 90_000,
  expressionRerollMaxMs: 180_000,
  /** Layer C: how often an ambient whole-image transform plays. */
  ambientMinMs: 60_000,
  ambientMaxMs: 120_000,
  ambientStretchMs: 900,
  ambientWobbleMs: 900,
  /** Layer D: how long a capture reaction holds before reverting to Layer B's pick. */
  reactionDurationMs: 2500,
  /** Crossfade duration between expression images — also set as a CSS var in index.css; keep in sync. */
  crossfadeMs: 700,
} as const;
