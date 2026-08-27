/**
 * features/goals/goalHierarchy.ts
 *
 * Pure, side-effect-free helpers shared by GoalsPage. Mirrors the backend's
 * tier-ordering rules exactly (productivity/models.py's GOAL_TIER_RANK and
 * goal_service.py's validate_parent_link) so the UI can pre-filter eligible
 * parents and avoid round-tripping to the server just to discover an
 * invalid combination — the server still re-validates on PATCH regardless
 * (never trust client-side validation as the only enforcement).
 */

import { GOAL_TIERS, type Goal, type GoalTier } from "../../shared/types";

const TIER_RANK: Record<GoalTier, number> = Object.fromEntries(
  GOAL_TIERS.map((tier, index) => [tier, index])
) as Record<GoalTier, number>;

export interface GoalTreeNode {
  goal: Goal;
  children: GoalTreeNode[];
}

/**
 * Splits goals into "untiered" (flat, MVP-style — no hierarchy
 * participation at all) and a forest of tiered goals rooted at whichever
 * tiered goals have no parent.
 */
export function buildGoalForest(goals: Goal[]): { untiered: Goal[]; forest: GoalTreeNode[] } {
  const untiered = goals.filter((g) => g.tier === null);
  const tiered = goals.filter((g) => g.tier !== null);

  const byId = new Map<string, GoalTreeNode>(tiered.map((g) => [g.id, { goal: g, children: [] }]));
  const forest: GoalTreeNode[] = [];

  for (const node of byId.values()) {
    const parentId = node.goal.parentGoalId;
    if (parentId && byId.has(parentId)) {
      byId.get(parentId)!.children.push(node);
    } else {
      // No parent, or parent isn't in this list (shouldn't happen given
      // the backend's referential integrity, but fails safe as a root
      // rather than silently dropping the goal from view).
      forest.push(node);
    }
  }

  return { untiered, forest };
}

/**
 * Which of the user's other goals could legally become `goal`'s parent —
 * same tier-ordering rule the backend enforces (strictly broader tier
 * only). Returns an empty list (not an error) if `goal` has no tier yet;
 * the UI should prompt for a tier first in that case, matching the
 * backend's own error message.
 */
export function eligibleParents(goal: Goal, allGoals: Goal[]): Goal[] {
  if (!goal.tier) return [];
  const ownRank = TIER_RANK[goal.tier];
  return allGoals.filter(
    (candidate) => candidate.id !== goal.id && candidate.tier !== null && TIER_RANK[candidate.tier] < ownRank
  );
}
