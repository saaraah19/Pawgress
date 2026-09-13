import { forwardRef, useEffect, useImperativeHandle, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useAuth } from "../auth/AuthContext";
import { getCompanionState } from "../../api/client";
import { COMPANION_QUERY_KEY } from "../../shared/queryKeys";
import { useCompanionBehavior } from "./useCompanionBehavior";
import { COMPANION_EXPRESSION_ASSETS, COMPANION_EXPRESSION_LABELS, COMPANION_TIMING, type CompanionExpressionKey } from "./companionConfig";

export interface CompanionCharacterHandle {
  reactToCapture: () => void;
}

interface CompanionCharacterProps {
  /**
   * Daily View scale (Sarah's explicit call, 2026-09-13: the original
   * 40px default read as too small once real art replaced the placeholder
   * glyph). No longer a header-scale default — the header doesn't mount
   * this component at all post-repositioning.
   */
  size?: number;
}

/**
 * FR-6.1 — the cat's visual reaction to activity, now backed by the real
 * production character (docs/companion-character-spec.md) instead of the
 * placeholder paw glyph. Replaces CompanionIndicator entirely (that
 * component has since been removed as dead code).
 *
 * Relocated from the app-wide header into the Daily View (CapturePage),
 * near the task list, per the owner's explicit positioning decision — it
 * is no longer rendered on every page. AppShell no longer mounts this or
 * the CompanionReactionContext bridge; CapturePage owns the instance and
 * its ref directly now that the event (a successful capture) and the
 * component live on the same page.
 *
 * Renders whichever of the 7 flattened expression images
 * useCompanionBehavior currently selects, cross-fading between them with
 * two stacked <img> layers — a flattened PNG swap can't crossfade via a
 * single background-image transition, so this needs two layers rather
 * than one. Silent (renders nothing) until mood has loaded — a loading
 * spinner or error state for a peripheral, non-essential element would
 * give it more visual weight than it's supposed to have (Blueprint §4:
 * "silence is a valid design choice").
 *
 * Accessibility: the wrapping element carries `role="img"` and a real
 * `aria-label` (COMPANION_EXPRESSION_LABELS) so the companion's current
 * expression is actually exposed to assistive tech — previously it had
 * no accessible name at all (both image layers are aria-hidden, and a
 * non-interactive element's `title` attribute isn't reliably announced).
 */
export const CompanionCharacter = forwardRef<CompanionCharacterHandle, CompanionCharacterProps>(
  function CompanionCharacter({ size = 110 }, ref) {
    const { token } = useAuth();

    const query = useQuery({
      queryKey: COMPANION_QUERY_KEY,
      queryFn: () => getCompanionState(token!),
      enabled: !!token,
      staleTime: 60_000,
    });

    const behavior = useCompanionBehavior(query.data?.mood);

    useImperativeHandle(ref, () => ({ reactToCapture: behavior.reactToCapture }), [behavior.reactToCapture]);

    const [displayed, setDisplayed] = useState<CompanionExpressionKey | null>(null);
    const [incoming, setIncoming] = useState<CompanionExpressionKey | null>(null);
    const swapTimerRef = useRef<ReturnType<typeof setTimeout>>();

    useEffect(() => {
      if (!query.data) return;
      const next = behavior.expression;

      if (displayed === null) {
        setDisplayed(next);
        return;
      }
      if (next === displayed || next === incoming) return;

      setIncoming(next);
      swapTimerRef.current = setTimeout(() => {
        setDisplayed(next);
        setIncoming(null);
      }, COMPANION_TIMING.crossfadeMs);

      return () => clearTimeout(swapTimerRef.current);
      // Only the selected expression (and data-loaded gate) should drive a
      // swap — `displayed`/`incoming` are intentionally excluded so this
      // doesn't re-run every time the crossfade itself updates state.
      // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [behavior.expression, query.data]);

    if (!query.data || displayed === null) {
      return null;
    }

    return (
      <span
        className="companion-character"
        style={{ width: size, height: size }}
        role="img"
        aria-label={COMPANION_EXPRESSION_LABELS[displayed]}
      >
        <img
          className={`companion-character-layer companion-character-ambient-${behavior.ambientAnimation}`}
          src={COMPANION_EXPRESSION_ASSETS[displayed]}
          alt=""
          aria-hidden="true"
        />
        {incoming && (
          <img
            className="companion-character-layer companion-character-layer-incoming"
            src={COMPANION_EXPRESSION_ASSETS[incoming]}
            alt=""
            aria-hidden="true"
          />
        )}
      </span>
    );
  }
);
