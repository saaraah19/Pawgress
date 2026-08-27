/**
 * features/companion/useCompanionBehavior.ts
 *
 * Implements companion-character-spec.md §5's four behavior layers, scoped
 * to what v1's flattened-PNG assets actually support:
 *
 *  A — backend mood (Neutral/Attentive/Content). NOT fetched here — passed
 *      in as a plain argument, so this hook stays testable without a
 *      network mock and has no opinion on how the caller sources it.
 *  B — frontend personality/expression state: weighted random selection
 *      over COMPANION_EXPRESSION_WEIGHTS, never a lookup table. Rerolls
 *      immediately on mood change, plus its own slower independent cadence.
 *  C — mood-independent ambient timer: layers a whole-image transform
 *      (stretch or wobble) on top of whatever's showing, on a loose,
 *      infrequent cadence. Skipped entirely under prefers-reduced-motion.
 *  D — event-driven contextual reaction (reactToCapture). Takes priority
 *      over B while active, then hands control back automatically.
 *
 * Explicitly NOT implemented: any blink/gaze-shift/ear-twitch/tail-flick
 * (needs separated layers the v1 assets don't have — see
 * companion-character-spec.md §6), and any behavior driven by elapsed time
 * since last activity (FR-6.2 / UX Philosophy §5.5 — Return-After-Absence
 * gets zero special treatment). This hook never reads a clock except to
 * schedule its own next reroll/ambient tick; it never computes "how long
 * since" anything.
 */

import { useCallback, useEffect, useRef, useState } from "react";
import type { CatMoodState } from "../../shared/types";
import {
  COMPANION_EXPRESSION_WEIGHTS,
  COMPANION_REACTION_WEIGHTS,
  COMPANION_TIMING,
  type CompanionExpressionKey,
} from "./companionConfig";

function pickWeighted(weights: Partial<Record<CompanionExpressionKey, number>>): CompanionExpressionKey {
  const entries = Object.entries(weights) as [CompanionExpressionKey, number][];
  const total = entries.reduce((sum, [, weight]) => sum + weight, 0);
  let roll = Math.random() * total;
  for (const [key, weight] of entries) {
    roll -= weight;
    if (roll <= 0) return key;
  }
  return entries[entries.length - 1][0];
}

function randomDelay(minMs: number, maxMs: number): number {
  return minMs + Math.random() * (maxMs - minMs);
}

export type AmbientAnimation = "none" | "stretch" | "wobble";

export interface CompanionBehaviorState {
  /** Which of the 7 flattened images should be showing right now. */
  expression: CompanionExpressionKey;
  /** Whole-image transform currently layered on top, independent of expression. */
  ambientAnimation: AmbientAnimation;
  /**
   * Layer D. Call after a successful capture. Briefly biases the displayed
   * expression toward alertness, then reverts on its own. A no-op if a
   * reaction is already in progress (never stacks or restarts the clock).
   */
  reactToCapture: () => void;
  /**
   * Reserved. Not implemented — the real trigger condition (e.g. "task
   * circled back to multiple times") needs status-history tracking that
   * does not exist in the domain model yet (companion-character-spec.md
   * §4.3: "architecturally reserved, not built"). Calling this today does
   * nothing. It exists purely so a future slice can wire in real behavior
   * without changing this hook's public interface.
   */
  triggerEarnedDelight: () => void;
}

export function useCompanionBehavior(mood: CatMoodState | undefined): CompanionBehaviorState {
  const [baseExpression, setBaseExpression] = useState<CompanionExpressionKey>("calm");
  const [reactionExpression, setReactionExpression] = useState<CompanionExpressionKey | null>(null);
  const [ambientAnimation, setAmbientAnimation] = useState<AmbientAnimation>("none");

  const rerollTimerRef = useRef<ReturnType<typeof setTimeout>>();
  const ambientTimerRef = useRef<ReturnType<typeof setTimeout>>();
  const ambientClearRef = useRef<ReturnType<typeof setTimeout>>();
  const reactionTimerRef = useRef<ReturnType<typeof setTimeout>>();

  // Layer B.
  useEffect(() => {
    if (!mood) return;

    let cancelled = false;

    function reroll() {
      setBaseExpression(pickWeighted(COMPANION_EXPRESSION_WEIGHTS[mood as CatMoodState]));
      rerollTimerRef.current = setTimeout(() => {
        if (!cancelled) reroll();
      }, randomDelay(COMPANION_TIMING.expressionRerollMinMs, COMPANION_TIMING.expressionRerollMaxMs));
    }
    reroll();

    return () => {
      cancelled = true;
      clearTimeout(rerollTimerRef.current);
    };
  }, [mood]);

  // Layer C. Same reduced-motion guard pattern as the prior CompanionIndicator:
  // no timers scheduled at all, not just a CSS override, for someone who's
  // opted out of motion.
  useEffect(() => {
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
      return;
    }

    let cancelled = false;

    function scheduleNext() {
      ambientTimerRef.current = setTimeout(() => {
        if (cancelled) return;
        const kind: AmbientAnimation = Math.random() < 0.5 ? "stretch" : "wobble";
        setAmbientAnimation(kind);
        const clearAfter = kind === "stretch" ? COMPANION_TIMING.ambientStretchMs : COMPANION_TIMING.ambientWobbleMs;
        ambientClearRef.current = setTimeout(() => {
          if (!cancelled) setAmbientAnimation("none");
        }, clearAfter);
        scheduleNext();
      }, randomDelay(COMPANION_TIMING.ambientMinMs, COMPANION_TIMING.ambientMaxMs));
    }
    scheduleNext();

    return () => {
      cancelled = true;
      clearTimeout(ambientTimerRef.current);
      clearTimeout(ambientClearRef.current);
    };
  }, []);

  const reactToCapture = useCallback(() => {
    if (reactionTimerRef.current) return;
    setReactionExpression(pickWeighted(COMPANION_REACTION_WEIGHTS));
    reactionTimerRef.current = setTimeout(() => {
      setReactionExpression(null);
      reactionTimerRef.current = undefined;
    }, COMPANION_TIMING.reactionDurationMs);
  }, []);

  const triggerEarnedDelight = useCallback(() => {
    // Reserved — see docstring above. Intentionally empty.
  }, []);

  // Cleanup on unmount.
  useEffect(() => {
    return () => {
      clearTimeout(rerollTimerRef.current);
      clearTimeout(ambientTimerRef.current);
      clearTimeout(ambientClearRef.current);
      clearTimeout(reactionTimerRef.current);
    };
  }, []);

  return {
    expression: reactionExpression ?? baseExpression,
    ambientAnimation,
    reactToCapture,
    triggerEarnedDelight,
  };
}
