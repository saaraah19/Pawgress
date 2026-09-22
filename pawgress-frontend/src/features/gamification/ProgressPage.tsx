import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useAuth } from "../auth/AuthContext";
import { getGamificationState } from "../../api/client";
import { GAMIFICATION_QUERY_KEY } from "../../shared/queryKeys";
import { getStoredThemeAccent, setStoredThemeAccent } from "./themeAccents";
import type { UnlockableItem } from "../../shared/types";

/**
 * XP/Level (2026-09-16) — Blueprint §13's already-approved V2 item,
 * built now that the core loop is proven. Everything shown here is
 * computed live from real Task/Habit completions (gamification/catalog.py's
 * docstring) — there's nothing to "sync," it's always current.
 *
 * Deliberately no streak, no leaderboard, no comparison to anyone else,
 * no way for any number on this page to go down. Unlockables are
 * cosmetic-only (a UI accent color, a display-only badge) — nothing here
 * changes what the app can do, only how a couple of small things look.
 */
export function ProgressPage() {
  const { token } = useAuth();
  const [activeAccent, setActiveAccent] = useState(getStoredThemeAccent());

  const query = useQuery({
    queryKey: GAMIFICATION_QUERY_KEY,
    queryFn: () => getGamificationState(token!),
    enabled: !!token,
  });

  function selectAccent(item: UnlockableItem) {
    if (!item.unlocked) return;
    setStoredThemeAccent(item.id);
    setActiveAccent(item.id);
  }

  const state = query.data;
  const progressPercent =
    state && state.xpForNextLevel > state.xpForCurrentLevel
      ? Math.min(
          100,
          Math.round(
            ((state.xp - state.xpForCurrentLevel) / (state.xpForNextLevel - state.xpForCurrentLevel)) * 100
          )
        )
      : 0;

  const themeItems = state?.items.filter((i) => i.kind === "theme_accent") ?? [];
  const badgeItems = state?.items.filter((i) => i.kind === "badge") ?? [];

  return (
    <div className="page">
      <div className="card progress-card">
        <h1>Progress</h1>

        {query.isLoading && <p className="muted">Loading...</p>}

        {query.isError && (
          <div className="notice">
            Couldn't load this just now.{" "}
            <button className="link" onClick={() => query.refetch()}>
              Try again
            </button>
          </div>
        )}

        {state && (
          <>
            <div className="progress-level-block">
              <span className="progress-level-number">Level {state.level}</span>
              <div className="progress-bar-track">
                <div className="progress-bar-fill" style={{ width: `${progressPercent}%` }} />
              </div>
              <span className="progress-xp-label">
                {state.xp} / {state.xpForNextLevel} XP
              </span>
            </div>

            <section className="progress-section">
              <h2>Accent color</h2>
              <div className="progress-item-grid">
                {themeItems.map((item) => (
                  <button
                    key={item.id}
                    type="button"
                    className={`progress-item${item.unlocked ? "" : " is-locked"}${
                      activeAccent === item.id ? " is-selected" : ""
                    }`}
                    disabled={!item.unlocked}
                    onClick={() => selectAccent(item)}
                    aria-pressed={activeAccent === item.id}
                  >
                    <span className="progress-item-name">{item.name}</span>
                    <span className="progress-item-detail">
                      {item.unlocked ? item.description : `Unlocks at level ${item.unlockLevel}`}
                    </span>
                  </button>
                ))}
              </div>
            </section>

            <section className="progress-section">
              <h2>Badges</h2>
              <div className="progress-item-grid">
                {badgeItems.map((item) => (
                  <div key={item.id} className={`progress-item${item.unlocked ? "" : " is-locked"}`}>
                    <span className="progress-item-name">{item.name}</span>
                    <span className="progress-item-detail">
                      {item.unlocked ? item.description : `Unlocks at level ${item.unlockLevel}`}
                    </span>
                  </div>
                ))}
              </div>
            </section>
          </>
        )}
      </div>
    </div>
  );
}
