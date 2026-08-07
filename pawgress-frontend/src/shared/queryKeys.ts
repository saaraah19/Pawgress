/**
 * Centralized query keys, shared between TaskList and GoalsPage — deleting
 * a Goal requires invalidating Task data too (unlink, not cascade, per
 * Domain Model Invariant 9), so both live here rather than each feature
 * file defining and cross-importing the other's key.
 */
export const TASKS_QUERY_KEY = ["tasks"] as const;
export const GOALS_QUERY_KEY = ["goals"] as const;
export const COMPANION_QUERY_KEY = ["companion", "state"] as const;
export const PROFILE_QUERY_KEY = ["profile"] as const;