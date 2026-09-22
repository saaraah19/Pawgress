/**
 * features/gamification/levelUpNotice.ts
 *
 * Tracks "the last level this browser has already seen," client-side
 * only (localStorage) — same reasoning as themeAccents.ts's stored
 * accent: no stated cross-device sync requirement, so no reason to add
 * backend persistence for it. This is what makes the level-up
 * acknowledgment fire exactly once per level, not on every page load.
 *
 * Deliberately does NOT fire on first-ever load for a user who's already
 * past level 1 (e.g. gamification shipped after they'd already
 * accumulated completions) — first load just silently records the
 * current level as "seen," so nobody gets a false "congratulations" for
 * progress they made before this feature existed. Same instinct as
 * mood_calculator.py never treating a brand-new user's zero-signal state
 * as something worth commenting on.
 */

const STORAGE_KEY = "pawgress:last-seen-level";

/** Returns the level to announce, or null if nothing new to announce.
 * Always updates the stored value as a side effect — call this at most
 * once per fetch, not on every render. */
export function checkForLevelUp(currentLevel: number): number | null {
  const stored = localStorage.getItem(STORAGE_KEY);

  if (stored === null) {
    localStorage.setItem(STORAGE_KEY, String(currentLevel));
    return null;
  }

  const lastSeen = Number(stored);
  if (currentLevel > lastSeen) {
    localStorage.setItem(STORAGE_KEY, String(currentLevel));
    return currentLevel;
  }

  return null;
}
