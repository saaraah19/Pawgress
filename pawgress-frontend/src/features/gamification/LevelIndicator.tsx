import { useEffect } from "react";
import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { useAuth } from "../auth/AuthContext";
import { getGamificationState } from "../../api/client";
import { GAMIFICATION_QUERY_KEY } from "../../shared/queryKeys";
import { useToast } from "../../shared/ui/ToastProvider";
import { checkForLevelUp } from "./levelUpNotice";

/**
 * Small, quiet, next to the companion on the Daily View — not a
 * dashboard widget, not a progress-bar-as-centerpiece. Same restraint
 * principle Brand §10 applies to the cat's ambient presence, applied
 * here to a different small element sharing the same corner of the
 * screen. Tap through to /progress for the full picture (level bar,
 * accent picker, badge shelf).
 *
 * Also owns the level-up acknowledgment (2026-09-16) — a single quiet
 * toast, once per level, never a modal or a "confetti-cannon" moment.
 * Brand §10 is explicit even about the BIGGEST earned-delight reactions:
 * "no confetti-cannon energy, no achievement-unlocked chrome." Levels
 * happen often early on (level 2 is just 10 completions) — frequent
 * enough that treating each one as a big event would cheapen the ones
 * that are genuinely rare, the same failure mode Brand §10 warns
 * against for the cat's own reactions. So: same toast system already
 * used for ordinary things (undo confirmations), same plain tone, no
 * exclamation point, named specifically (which item unlocked, if any)
 * rather than a generic "Great job!" — Brand §5's specificity principle
 * applied to this instead of praise copy.
 */
export function LevelIndicator() {
  const { token } = useAuth();
  const { showToast } = useToast();

  const query = useQuery({
    queryKey: GAMIFICATION_QUERY_KEY,
    queryFn: () => getGamificationState(token!),
    enabled: !!token,
  });

  useEffect(() => {
    if (!query.data) return;
    const newLevel = checkForLevelUp(query.data.level);
    if (newLevel === null) return;

    const unlockedHere = query.data.items.find((item) => item.unlockLevel === newLevel);
    showToast({
      message: unlockedHere ? `Level ${newLevel} — ${unlockedHere.name} unlocked.` : `Level ${newLevel}.`,
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [query.data?.level]);

  if (!query.data) return null;

  return (
    <Link to="/progress" className="level-indicator" aria-label={`Level ${query.data.level}. View progress.`}>
      Lvl {query.data.level}
    </Link>
  );
}
