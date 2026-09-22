import { describe, it, expect, beforeEach } from "vitest";
import { checkForLevelUp } from "./levelUpNotice";

const STORAGE_KEY = "pawgress:last-seen-level";

describe("checkForLevelUp", () => {
  beforeEach(() => {
    localStorage.clear();
  });

  it("does not announce anything on the very first check (nothing seen yet)", () => {
    // Prevents a false "congratulations" for progress made before this
    // feature existed — first load just silently records the current
    // level as seen (levelUpNotice.ts's own docstring).
    expect(checkForLevelUp(5)).toBeNull();
    expect(localStorage.getItem(STORAGE_KEY)).toBe("5");
  });

  it("announces when the level increases since last seen", () => {
    checkForLevelUp(3); // first call, establishes baseline
    const result = checkForLevelUp(4);
    expect(result).toBe(4);
  });

  it("does not announce again for the same level", () => {
    checkForLevelUp(3);
    checkForLevelUp(4); // announced once
    expect(checkForLevelUp(4)).toBeNull(); // same level again — silent
  });

  it("does not announce when the level has not changed at all", () => {
    checkForLevelUp(2);
    expect(checkForLevelUp(2)).toBeNull();
  });

  it("updates the stored value so a later increase is measured from the new level, not the original one", () => {
    checkForLevelUp(1);
    checkForLevelUp(2);
    expect(checkForLevelUp(3)).toBe(3);
    // Confirms it wasn't still comparing against level 1.
    expect(checkForLevelUp(3)).toBeNull();
  });
});
