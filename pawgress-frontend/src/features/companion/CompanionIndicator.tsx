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
 * sidesteps that entirely by living somewhere else). No animation, no
 * icon beyond a small glyph — visual richness here is a design-phase
 * deliverable (Brand §7), not something to invent now.
 *
 * Cat-voiced copy only (Brand §4): sparse, low-key, never explains itself,
 * never delivers anything the user needs to trust as correct. If this
 * fails to load, it renders nothing at all — silence is a valid design
 * choice (Blueprint §4), and a loading spinner or error notice for a
 * peripheral, non-essential element would give it more visual weight than
 * it's supposed to have.
 */
const MOOD_COPY: Record<CatMoodState, string> = {
  Neutral: "settling in",
  Attentive: "keeping watch",
  Content: "here with you today",
};

export function CompanionIndicator() {
  const { token } = useAuth();

  const query = useQuery({
    queryKey: COMPANION_QUERY_KEY,
    queryFn: () => getCompanionState(token!),
    enabled: !!token,
    staleTime: 60_000,
  });

  if (!query.data) {
    return null;
  }

  return (
    <span className="companion-indicator" title="Your companion">
      <span className="companion-glyph" aria-hidden="true">
        🐾
      </span>
      <span className="companion-copy">{MOOD_COPY[query.data.mood]}</span>
    </span>
  );
}
