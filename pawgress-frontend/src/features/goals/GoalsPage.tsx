import { useEffect, useRef, useState, type FormEvent } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useAuth } from "../auth/AuthContext";
import { createGoal, listGoals, updateGoal, deleteGoal } from "../../api/client";
import { useToast } from "../../shared/ui/ToastProvider";
import { GOALS_QUERY_KEY, TASKS_QUERY_KEY } from "../../shared/queryKeys";
import { GOAL_TIERS } from "../../shared/types";
import type { Goal, GoalTier, GoalUpdateRequest } from "../../shared/types";
import { ApiError } from "../../api/client";
import { buildGoalForest } from "./goalHierarchy";
import { GoalNode } from "./GoalNode";

const UNDO_WINDOW_MS = 5000;

/**
 * FR-5.1 (create/list/delete, flat labels) extended for V2 full goal
 * hierarchy (Blueprint §13). Goals with no tier render exactly as the old
 * MVP flat list did — hierarchy is opt-in, never assumed (Domain Model
 * §4.3), so a user who ignores tiers entirely sees no change at all.
 *
 * Tiered goals render as a nested tree instead, built client-side by
 * goalHierarchy.ts from the same flat GET /goals response — no separate
 * endpoint or nested API shape needed, since the whole tree is small
 * enough to reconstruct locally at MVP/V2 scale.
 *
 * Deletion keeps the same instant-delete-plus-undo pattern already used
 * elsewhere (shared/ui/ToastProvider.tsx) — no confirmation dialog,
 * consistent with the rest of the app.
 */
export function GoalsPage() {
  const { token } = useAuth();
  const queryClient = useQueryClient();
  const { showToast } = useToast();
  const [label, setLabel] = useState("");
  const [newTier, setNewTier] = useState<GoalTier | "">("");
  const [pendingDeleteIds, setPendingDeleteIds] = useState<Set<string>>(new Set());
  const deleteTimers = useRef<Map<string, ReturnType<typeof setTimeout>>>(new Map());
  const [updateError, setUpdateError] = useState<{ goalId: string; message: string } | null>(null);

  const goalsQuery = useQuery({
    queryKey: GOALS_QUERY_KEY,
    queryFn: () => listGoals(token!),
    enabled: !!token,
  });

  const createMutation = useMutation({
    mutationFn: () => createGoal({ label: label.trim(), tier: newTier || undefined }, token!),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: GOALS_QUERY_KEY });
      setLabel("");
      setNewTier("");
    },
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, patch }: { id: string; patch: GoalUpdateRequest }) => updateGoal(id, patch, token!),
    onSuccess: () => {
      setUpdateError(null);
      queryClient.invalidateQueries({ queryKey: GOALS_QUERY_KEY });
    },
    onError: (err, variables) => {
      setUpdateError({
        goalId: variables.id,
        message: err instanceof ApiError ? err.message : "Couldn't make that change just now.",
      });
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => deleteGoal(id, token!),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: GOALS_QUERY_KEY });
      queryClient.invalidateQueries({ queryKey: TASKS_QUERY_KEY });
    },
  });

  useEffect(() => {
    return () => {
      deleteTimers.current.forEach((timer, id) => {
        clearTimeout(timer);
        deleteMutation.mutate(id);
      });
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function handleDeleteClick(goal: Goal) {
    setPendingDeleteIds((prev) => new Set(prev).add(goal.id));

    const timer = setTimeout(() => {
      deleteMutation.mutate(goal.id);
      deleteTimers.current.delete(goal.id);
      setPendingDeleteIds((prev) => {
        const next = new Set(prev);
        next.delete(goal.id);
        return next;
      });
    }, UNDO_WINDOW_MS);
    deleteTimers.current.set(goal.id, timer);

    showToast({
      message: `"${goal.label}" deleted`,
      actionLabel: "Undo",
      durationMs: UNDO_WINDOW_MS,
      onAction: () => {
        const pendingTimer = deleteTimers.current.get(goal.id);
        if (pendingTimer) {
          clearTimeout(pendingTimer);
          deleteTimers.current.delete(goal.id);
        }
        setPendingDeleteIds((prev) => {
          const next = new Set(prev);
          next.delete(goal.id);
          return next;
        });
      },
    });
  }

  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    const trimmed = label.trim();
    if (!trimmed) return;
    createMutation.mutate();
  }

  const allGoals = goalsQuery.data ?? [];
  const visibleGoals = allGoals.filter((g) => !pendingDeleteIds.has(g.id));
  const { untiered, forest } = buildGoalForest(visibleGoals);

  return (
    <div className="page">
      <div className="card goals-card">
        <h1>Goals</h1>

        <form onSubmit={handleSubmit} className="capture-form">
          <input
            className="field-inline"
            placeholder="Add a goal"
            aria-label="New goal"
            value={label}
            disabled={createMutation.isPending}
            onChange={(e) => setLabel(e.target.value)}
          />
          <select
            className="field-inline field-priority"
            value={newTier}
            disabled={createMutation.isPending}
            aria-label="Tier for new goal (optional)"
            onChange={(e) => setNewTier(e.target.value as GoalTier | "")}
          >
            <option value="">No tier</option>
            {GOAL_TIERS.map((t) => (
              <option key={t} value={t}>
                {t}
              </option>
            ))}
          </select>
          <button className="primary" type="submit" disabled={createMutation.isPending || !label.trim()}>
            Add
          </button>
        </form>

        {goalsQuery.isLoading && <p className="muted">Loading goals...</p>}

        {goalsQuery.isError && (
          <div className="notice">
            Couldn't load your goals just now.{" "}
            <button className="link" onClick={() => goalsQuery.refetch()}>
              Try again
            </button>
          </div>
        )}

        {goalsQuery.data && visibleGoals.length === 0 && <p className="empty-state">No goals yet.</p>}

        {forest.length > 0 && (
          <>
            <h2 className="goals-section-heading">Hierarchy</h2>
            <ul className="goal-tree">
              {forest.map((node) => (
                <GoalNode
                  key={node.goal.id}
                  node={node}
                  allGoals={allGoals}
                  depth={0}
                  onUpdate={(id, patch) => updateMutation.mutate({ id, patch })}
                  onDelete={handleDeleteClick}
                  savingId={updateMutation.isPending ? updateMutation.variables?.id ?? null : null}
                  error={updateError}
                />
              ))}
            </ul>
          </>
        )}

        {untiered.length > 0 && (
          <>
            {forest.length > 0 && <h2 className="goals-section-heading">Untiered</h2>}
            <ul className="task-list">
              {untiered.map((goal) => (
                <li key={goal.id} className="task-row">
                  <span className="task-title">{goal.label}</span>
                  <select
                    className="field-inline field-priority"
                    value=""
                    disabled={updateMutation.isPending && updateMutation.variables?.id === goal.id}
                    aria-label={`Give "${goal.label}" a tier`}
                    onChange={(e) => {
                      if (e.target.value) {
                        updateMutation.mutate({ id: goal.id, patch: { tier: e.target.value as GoalTier } });
                      }
                    }}
                  >
                    <option value="">Add to hierarchy...</option>
                    {GOAL_TIERS.map((t) => (
                      <option key={t} value={t}>
                        {t}
                      </option>
                    ))}
                  </select>
                  <button
                    type="button"
                    className="link task-delete"
                    onClick={() => handleDeleteClick(goal)}
                    aria-label={`Delete goal "${goal.label}"`}
                  >
                    Delete
                  </button>
                </li>
              ))}
            </ul>
          </>
        )}
      </div>
    </div>
  );
}
