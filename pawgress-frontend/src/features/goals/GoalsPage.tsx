import { useEffect, useRef, useState, type FormEvent } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useAuth } from "../auth/AuthContext";
import { createGoal, listGoals, deleteGoal } from "../../api/client";
import { useToast } from "../../shared/ui/ToastProvider";
import { EmptyState } from "../../shared/ui/EmptyState";
import { GOALS_QUERY_KEY, TASKS_QUERY_KEY } from "../../shared/queryKeys";
import type { Goal } from "../../shared/types";

const UNDO_WINDOW_MS = 5000;

/**
 * FR-5.1: create/list/delete goals — flat labels, no sub-structure.
 * Deleting a goal unlinks (never cascades to) any task that referenced it
 * (Domain Model Invariant 9), so tasks are invalidated on delete too, to
 * pick up the cleared goalId rather than showing a stale link.
 *
 * Delete uses the same instant-delete-plus-undo pattern as TaskList
 * (shared/ui/ToastProvider.tsx) rather than a confirmation dialog —
 * consistency pass: the two delete affordances in the app should feel
 * identical, not like two different products' conventions. Undo is
 * simpler here than it looks: because the actual DELETE call (and the
 * unlink it triggers) is deferred until the grace window elapses, "Undo"
 * just cancels that timer — nothing has touched the server yet, so
 * there's no unlink to reverse.
 */
export function GoalsPage() {
  const { token } = useAuth();
  const queryClient = useQueryClient();
  const { showToast } = useToast();
  const [label, setLabel] = useState("");
  const [pendingDeleteIds, setPendingDeleteIds] = useState<Set<string>>(new Set());
  const deleteTimers = useRef<Map<string, ReturnType<typeof setTimeout>>>(new Map());

  const goalsQuery = useQuery({
    queryKey: GOALS_QUERY_KEY,
    queryFn: () => listGoals(token!),
    enabled: !!token,
  });

  const createMutation = useMutation({
    mutationFn: (label: string) => createGoal(label, token!),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: GOALS_QUERY_KEY });
      setLabel("");
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
    createMutation.mutate(trimmed);
  }

  const visibleGoals = (goalsQuery.data ?? []).filter((g) => !pendingDeleteIds.has(g.id));

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

        {goalsQuery.data && visibleGoals.length === 0 && (
          <EmptyState mood="alert" message="Nothing to chase yet." />
        )}

        {visibleGoals.length > 0 && (
          <ul className="task-list">
            {visibleGoals.map((goal) => (
              <li key={goal.id} className="task-row">
                <span className="task-title">{goal.label}</span>
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
        )}
      </div>
    </div>
  );
}
