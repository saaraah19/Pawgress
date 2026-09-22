/**
 * features/gamification/themeAccents.ts
 *
 * Palette values for each unlockable theme_accent item — all chosen from
 * within the app's existing warm-neutral system (index.css's own comment:
 * red is "structurally absent... not implemented at all," which applies
 * here too — none of these read as a status/urgency color). "sage" is the
 * app's current default, reproduced here so switching back to it works
 * the same way as switching to any other unlocked accent.
 */

export interface AccentPalette {
  base: string;
  hover: string;
  tint: string;
}

export const THEME_ACCENT_PALETTES: Record<string, AccentPalette> = {
  "theme-sage": { base: "#2f4f4c", hover: "#24403d", tint: "#e2e9e7" },
  "theme-terracotta": { base: "#a15c3e", hover: "#8a4c31", tint: "#f0e2da" },
  "theme-dusty-blue": { base: "#4a6b7a", hover: "#3a5762", tint: "#e0e8ea" },
  "theme-golden": { base: "#b8894a", hover: "#9c7238", tint: "#f2e8d5" },
};

const STORAGE_KEY = "pawgress:active-theme-accent";

/** Client-side only, deliberately — a cosmetic preference with no stated
 * cross-device sync requirement, so persisting it server-side would be
 * schema surface area this feature doesn't need (gamification/catalog.py's
 * docstring: nothing about this feature is persisted server-side; this is
 * the one piece of client-only state that accompanies it). */
export function getStoredThemeAccent(): string {
  return localStorage.getItem(STORAGE_KEY) || "theme-sage";
}

export function setStoredThemeAccent(itemId: string): void {
  localStorage.setItem(STORAGE_KEY, itemId);
  applyThemeAccent(itemId);
}

export function applyThemeAccent(itemId: string): void {
  const palette = THEME_ACCENT_PALETTES[itemId] ?? THEME_ACCENT_PALETTES["theme-sage"];
  const root = document.documentElement.style;
  root.setProperty("--color-assistant", palette.base);
  root.setProperty("--color-assistant-hover", palette.hover);
  root.setProperty("--color-assistant-tint", palette.tint);
}

/** Call once at app startup so a previously-chosen accent survives a
 * refresh — see App.tsx. */
export function applyStoredThemeAccentOnLoad(): void {
  applyThemeAccent(getStoredThemeAccent());
}
