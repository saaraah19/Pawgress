import { useEffect, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useAuth } from "../auth/AuthContext";
import { getCompanionState } from "../../api/client";
import { COMPANION_QUERY_KEY } from "../../shared/queryKeys";
import type { CatMoodState } from "../../shared/types";

/**
 * FR-6.1 — the cat reacts to activity with a small number of distinct
 * states. Deliberately ambient: small, quiet, present in the header on
 * every page rather than inserted into the capture result flow (BR-3 — the
 * cat is never the primary visual focus of the First Capture moment; this
 * sidesteps that entirely by living somewhere else).
 *
 * Cat-voiced copy only (Brand §4): sparse, low-key, never explains itself,
 * never delivers anything the user needs to trust as correct. If this
 * fails to load, it renders nothing at all — silence is a valid design
 * choice (Blueprint §4), and a loading spinner or error notice for a
 * peripheral, non-essential element would give it more visual weight than
 * it's supposed to have.
 *
 * Two additions from the "make it feel alive" polish pass, both purely
 * client-side — neither introduces a new persisted CatMoodState (Domain
 * Model §7 keeps that enum small, closed, and presentation-only):
 *  - Several lines per mood instead of one fixed line, so the same mood
 *    doesn't read as a static label.
 *  - A rare, brief stretch animation layered on the glyph.
 */
const MOOD_COPY_VARIANTS: Record<CatMoodState, string[]> = {
  Neutral: ["settling in", "quietly here", "taking it in"],
  Attentive: ["keeping watch", "paying attention", "close by"],
  Content: ["here with you today", "glad to be here", "steady today"],
};

function pickRandom<T>(items: T[]): T {
  return items[Math.floor(Math.random() * items.length)];
}

export function CompanionIndicator() {
  const { token } = useAuth();
  const [isStretching, setIsStretching] = useState(false);

  const query = useQuery({
    queryKey: COMPANION_QUERY_KEY,
    queryFn: () => getCompanionState(token!),
    enabled: !!token,
    staleTime: 60_000,
  });

  const mood = query.data?.mood;

  // Rerolls only when the mood itself changes, not on every 60s
  // background refetch of an unchanged mood — that would make the copy
  // flicker for no reason, which reads as buggy, not alive.
  const copy = useMemo(() => (mood ? pickRandom(MOOD_COPY_VARIANTS[mood]) : null), [mood]);

  // A rare, brief stretch (every ~45–90s). Skipped entirely under
  // prefers-reduced-motion, rather than relying only on the CSS override,
  // so no timers run at all for someone who's opted out of motion.
  useEffect(() => {
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
      return;
    }
    let timeoutId: ReturnType<typeof setTimeout>;
    let stretchEndId: ReturnType<typeof setTimeout>;

    const scheduleNext = () => {
      const delay = 45_000 + Math.random() * 45_000;
      timeoutId = setTimeout(() => {
        setIsStretching(true);
        stretchEndId = setTimeout(() => setIsStretching(false), 900);
        scheduleNext();
      }, delay);
    };
    scheduleNext();

    return () => {
      clearTimeout(timeoutId);
      clearTimeout(stretchEndId);
    };
  }, []);

  if (!query.data || !copy) {
    return null;
  }

  return (
    <span className="companion-indicator" title="Your companion">
      <span className={`companion-glyph${isStretching ? " is-stretching" : ""}`} aria-hidden="true">
        🐾
      </span>
      <span className="companion-copy">{copy}</span>
    </span>
  );
}

