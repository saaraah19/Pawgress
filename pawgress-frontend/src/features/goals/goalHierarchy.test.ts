import { describe, it, expect } from "vitest";
import { buildGoalForest, eligibleParents } from "./goalHierarchy";
import type { Goal } from "../../shared/types";

function makeGoal(overrides: Partial<Goal> & { id: string }): Goal {
  return {
    label: "Untitled",
    tier: null,
    parentGoalId: null,
    createdAt: "2026-01-01T00:00:00Z",
    ...overrides,
  };
}

describe("buildGoalForest", () => {
  it("puts goals with no tier into the untiered bucket, never the forest", () => {
    const flat = makeGoal({ id: "1", label: "Someday maybe" });
    const { untiered, forest } = buildGoalForest([flat]);

    expect(untiered).toEqual([flat]);
    expect(forest).toEqual([]);
  });

  it("treats a tiered goal with no parent as a root", () => {
    const annual = makeGoal({ id: "1", label: "2027", tier: "Annual" });
    const { forest } = buildGoalForest([annual]);

    expect(forest).toHaveLength(1);
    expect(forest[0].goal.id).toBe("1");
    expect(forest[0].children).toEqual([]);
  });

  it("nests a child under its parent, not as a second root", () => {
    const annual = makeGoal({ id: "annual", tier: "Annual" });
    const project = makeGoal({ id: "project", tier: "Project", parentGoalId: "annual" });
    const { forest } = buildGoalForest([annual, project]);

    expect(forest).toHaveLength(1);
    expect(forest[0].goal.id).toBe("annual");
    expect(forest[0].children).toHaveLength(1);
    expect(forest[0].children[0].goal.id).toBe("project");
  });

  it("supports a Milestone attaching directly to an Annual goal, skipping intermediate tiers", () => {
    // Domain Model §4.3 — hierarchy is opt-in and doesn't need to be fully
    // populated; a user shouldn't be forced through every tier.
    const annual = makeGoal({ id: "annual", tier: "Annual" });
    const milestone = makeGoal({ id: "milestone", tier: "Milestone", parentGoalId: "annual" });
    const { forest } = buildGoalForest([annual, milestone]);

    expect(forest[0].children[0].goal.id).toBe("milestone");
  });

  it("falls back to treating a goal as a root if its declared parent isn't in the list", () => {
    // Fails safe rather than silently dropping the goal from view — the
    // backend's referential integrity means this shouldn't normally
    // happen, but the UI shouldn't lose data if it somehow does.
    const orphan = makeGoal({ id: "orphan", tier: "Project", parentGoalId: "does-not-exist" });
    const { forest } = buildGoalForest([orphan]);

    expect(forest).toHaveLength(1);
    expect(forest[0].goal.id).toBe("orphan");
  });

  it("handles a mix of untiered and multi-level tiered goals together", () => {
    const flat = makeGoal({ id: "flat", label: "Just a note" });
    const annual = makeGoal({ id: "annual", tier: "Annual" });
    const quarterly = makeGoal({ id: "quarterly", tier: "Quarterly", parentGoalId: "annual" });
    const project = makeGoal({ id: "project", tier: "Project", parentGoalId: "quarterly" });

    const { untiered, forest } = buildGoalForest([flat, annual, quarterly, project]);

    expect(untiered).toEqual([flat]);
    expect(forest).toHaveLength(1);
    expect(forest[0].children[0].goal.id).toBe("quarterly");
    expect(forest[0].children[0].children[0].goal.id).toBe("project");
  });
});

describe("eligibleParents", () => {
  it("returns nothing for a goal with no tier — there's no rank to compare", () => {
    const flat = makeGoal({ id: "flat" });
    const annual = makeGoal({ id: "annual", tier: "Annual" });

    expect(eligibleParents(flat, [flat, annual])).toEqual([]);
  });

  it("excludes untiered goals as candidates — they have no rank either", () => {
    const project = makeGoal({ id: "project", tier: "Project" });
    const flat = makeGoal({ id: "flat" });

    expect(eligibleParents(project, [project, flat])).toEqual([]);
  });

  it("excludes goals of the same or narrower tier — parent must be strictly broader", () => {
    const project = makeGoal({ id: "project", tier: "Project" });
    const anotherProject = makeGoal({ id: "project-2", tier: "Project" });
    const milestone = makeGoal({ id: "milestone", tier: "Milestone" });

    const candidates = eligibleParents(project, [project, anotherProject, milestone]);
    expect(candidates).toEqual([]);
  });

  it("includes any strictly broader tier, not just the immediately adjacent one", () => {
    const milestone = makeGoal({ id: "milestone", tier: "Milestone" });
    const annual = makeGoal({ id: "annual", tier: "Annual" });
    const quarterly = makeGoal({ id: "quarterly", tier: "Quarterly" });
    const project = makeGoal({ id: "project", tier: "Project" });

    const candidates = eligibleParents(milestone, [milestone, annual, quarterly, project]);
    const ids = candidates.map((c) => c.id).sort();
    expect(ids).toEqual(["annual", "project", "quarterly"]);
  });

  it("excludes the goal itself even if it somehow appears in the candidate list", () => {
    const annual = makeGoal({ id: "annual", tier: "Annual" });
    expect(eligibleParents(annual, [annual])).toEqual([]);
  });
});
