import { useState, type FormEvent } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useAuth } from "../auth/AuthContext";
import { createGoal, listGoals, deleteGoal } from "../../api/client";
import { GOALS_QUERY_KEY, TASKS_QUERY_KEY } from "../../shared/queryKeys";

/**
 * FR-5.1: create/list/delete goals — flat labels, no sub-structure.
 * Deleting a goal unlinks (never cascades to) any task that referenced it
 * (Domain Model Invariant 9), so tasks are invalidated on delete too, to
 * pick up the cleared goalId rather than showing a stale link.
 */
export function GoalsPage() {
  const { token } = useAuth();
  const queryClient = useQueryClient();
  const [label, setLabel] = useState("");

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

  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    const trimmed = label.trim();
    if (!trimmed) return;
    createMutation.mutate(trimmed);
  }

  return (
    <div className="page">
      <div className="card goals-card">
        <h1>Goals</h1>

        <form onSubmit={handleSubmit} className="capture-form">
          <input
            className="field-inline"
            placeholder="Add a goal"
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

        {goalsQuery.data && goalsQuery.data.length === 0 && (
          <p className="empty-state">No goals yet.</p>
        )}

        {goalsQuery.data && goalsQuery.data.length > 0 && (
          <ul className="task-list">
            {goalsQuery.data.map((goal) => (
              <li key={goal.id} className="task-row">
                <span className="task-title">{goal.label}</span>
                <button
                  type="button"
                  className="link"
                  disabled={deleteMutation.isPending && deleteMutation.variables === goal.id}
                  onClick={() => deleteMutation.mutate(goal.id)}
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