/**
 * Centralized query keys, shared between TaskList and GoalsPage — deleting
 * a Goal requires invalidating Task data too (unlink, not cascade, per
 * Domain Model Invariant 9), so both live here rather than each feature
 * file defining and cross-importing the other's key.
 */
export const TASKS_QUERY_KEY = ["tasks"] as const;
export const GOALS_QUERY_KEY = ["goals"] as const;