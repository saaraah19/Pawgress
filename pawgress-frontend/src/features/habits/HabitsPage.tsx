import { useEffect, useRef, useState, type FormEvent } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useAuth } from "../auth/AuthContext";
import {
  createHabit,
  listHabits,
  updateHabit,
  deleteHabit,
  markHabitComplete,
  unmarkHabitComplete,
  listGoals,
  ApiError,
} from "../../api/client";
import { useToast } from "../../shared/ui/ToastProvider";
import { HABITS_QUERY_KEY, GOALS_QUERY_KEY } from "../../shared/queryKeys";
import type { Goal, Habit, HabitFrequency } from "../../shared/types";

const UNDO_WINDOW_MS = 5000;

/** UTC-day ISO date string, matching the backend's today_utc() convention
 * (habits/models.py) — needed for the undo/unmark call, which requires an
 * explicit date rather than defaulting like the mark call does. */
function todayUtcIso(): string {
  return new Date().toISOString().slice(0, 10);
}

interface HabitRowProps {
  habit: Habit;
  linkedGoal: Goal | undefined;
  onToggle: () => void;
  onCommitLabel: (label: string) => void;
  onDelete: () => void;
  toggling: boolean;
  saving: boolean;
}

/** Same always-editable-input pattern as TaskRow.tsx: local state synced
 * from props, commits on blur if changed, no separate view/edit toggle. */
function HabitRow({ habit, linkedGoal, onToggle, onCommitLabel, onDelete, toggling, saving }: HabitRowProps) {
  const [label, setLabel] = useState(habit.label);

  useEffect(() => {
    setLabel(habit.label);
  }, [habit.label]);

  function commit() {
    const trimmed = label.trim();
    if (trimmed && trimmed !== habit.label) {
      onCommitLabel(trimmed);
    } else {
      setLabel(habit.label);
    }
  }

  return (
    <li className="habit-row">
      <button
        type="button"
        className={`habit-toggle${habit.completedToday ? " is-done" : ""}`}
        disabled={toggling}
        onClick={onToggle}
        aria-pressed={habit.completedToday}
        aria-label={habit.completedToday ? "Mark not done today" : "Mark done today"}
      >
        {habit.completedToday ? "✓" : ""}
      </button>
      <div className="habit-info">
        <input
          className="field-inline field-title"
          value={label}
          disabled={saving}
          onChange={(e) => setLabel(e.target.value)}
          onBlur={commit}
          onKeyDown={(e) => e.key === "Enter" && (e.target as HTMLInputElement).blur()}
        />
        <span className="habit-meta">
          {habit.frequency === "Daily" ? "Daily" : `${habit.weeklyTarget}x / week`}
          {" · "}
          done {habit.totalCompletions} {habit.totalCompletions === 1 ? "time" : "times"}
          {linkedGoal ? ` · ${linkedGoal.label}` : ""}
        </span>
      </div>
      <button type="button" className="link task-delete" onClick={onDelete} aria-label={`Delete "${habit.label}"`}>
        Delete
      </button>
    </li>
  );
}

/**
 * V2 Habits (Blueprint §13, §16). Deliberately shows NO streak counter —
 * progress is a plain accumulating total that never resets (see
 * habits/models.py's docstring for the full reasoning). No red, no
 * "broken" language, no indication anywhere of a missed day, because the
 * backend never even records one.
 */
export function HabitsPage() {
  const { token } = useAuth();
  const queryClient = useQueryClient();
  const { showToast } = useToast();

  const [label, setLabel] = useState("");
  const [frequency, setFrequency] = useState<HabitFrequency>("Daily");
  const [weeklyTarget, setWeeklyTarget] = useState("3");
  const [goalId, setGoalId] = useState("");
  const [formError, setFormError] = useState<string | null>(null);
  const [pendingDeleteIds, setPendingDeleteIds] = useState<Set<string>>(new Set());
  const deleteTimers = useRef<Map<string, ReturnType<typeof setTimeout>>>(new Map());

  const habitsQuery = useQuery({
    queryKey: HABITS_QUERY_KEY,
    queryFn: () => listHabits(token!),
    enabled: !!token,
  });

  const goalsQuery = useQuery({
    queryKey: GOALS_QUERY_KEY,
    queryFn: () => listGoals(token!),
    enabled: !!token,
  });

  const createMutation = useMutation({
    mutationFn: () =>
      createHabit(
        {
          label: label.trim(),
          frequency,
          weeklyTarget: frequency === "WeeklyCount" ? Number(weeklyTarget) : undefined,
          goalId: goalId || undefined,
        },
        token!
      ),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: HABITS_QUERY_KEY });
      setLabel("");
      setFrequency("Daily");
      setWeeklyTarget("3");
      setGoalId("");
      setFormError(null);
    },
    onError: (err) => {
      setFormError(err instanceof ApiError ? err.message : "Couldn't create that habit just now.");
    },
  });

  const toggleMutation = useMutation({
    mutationFn: (habit: Habit) =>
      habit.completedToday
        ? unmarkHabitComplete(habit.id, todayUtcIso(), token!)
        : markHabitComplete(habit.id, token!),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: HABITS_QUERY_KEY });
    },
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, label: newLabel }: { id: string; label: string }) =>
      updateHabit(id, { label: newLabel }, token!),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: HABITS_QUERY_KEY });
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => deleteHabit(id, token!),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: HABITS_QUERY_KEY });
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

  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (!label.trim() || createMutation.isPending) return;
    createMutation.mutate();
  }

  function handleDeleteClick(habit: Habit) {
    setPendingDeleteIds((prev) => new Set(prev).add(habit.id));

    const timer = setTimeout(() => {
      deleteMutation.mutate(habit.id);
      deleteTimers.current.delete(habit.id);
      setPendingDeleteIds((prev) => {
        const next = new Set(prev);
        next.delete(habit.id);
        return next;
      });
    }, UNDO_WINDOW_MS);
    deleteTimers.current.set(habit.id, timer);

    showToast({
      message: `"${habit.label}" deleted`,
      actionLabel: "Undo",
      durationMs: UNDO_WINDOW_MS,
      onAction: () => {
        const pendingTimer = deleteTimers.current.get(habit.id);
        if (pendingTimer) {
          clearTimeout(pendingTimer);
          deleteTimers.current.delete(habit.id);
        }
        setPendingDeleteIds((prev) => {
          const next = new Set(prev);
          next.delete(habit.id);
          return next;
        });
      },
    });
  }

  const goals = goalsQuery.data ?? [];
  const habits = (habitsQuery.data ?? []).filter((h) => !pendingDeleteIds.has(h.id));

  return (
    <div className="page">
      <div className="card habits-card">
        <h1>Habits</h1>

        <form onSubmit={handleSubmit} className="habit-form">
          <input
            className="field-inline"
            placeholder="Add a habit"
            aria-label="New habit"
            value={label}
            disabled={createMutation.isPending}
            onChange={(e) => setLabel(e.target.value)}
          />
          <div className="habit-form-row">
            <select
              className="field-inline field-priority"
              value={frequency}
              disabled={createMutation.isPending}
              aria-label="Frequency"
              onChange={(e) => setFrequency(e.target.value as HabitFrequency)}
            >
              <option value="Daily">Daily</option>
              <option value="WeeklyCount">X times a week</option>
            </select>
            {frequency === "WeeklyCount" && (
              <input
                className="field-inline field-estimate"
                type="number"
                min={1}
                max={7}
                value={weeklyTarget}
                disabled={createMutation.isPending}
                aria-label="Times per week"
                onChange={(e) => setWeeklyTarget(e.target.value)}
              />
            )}
            {goals.length > 0 && (
              <select
                className="field-inline field-priority"
                value={goalId}
                disabled={createMutation.isPending}
                aria-label="Link to a goal (optional)"
                onChange={(e) => setGoalId(e.target.value)}
              >
                <option value="">No goal</option>
                {goals.map((g) => (
                  <option key={g.id} value={g.id}>
                    {g.label}
                  </option>
                ))}
              </select>
            )}
            <button className="primary" type="submit" disabled={createMutation.isPending || !label.trim()}>
              Add
            </button>
          </div>
        </form>

        {formError && <div className="notice">{formError}</div>}

        {habitsQuery.isLoading && <p className="muted">Loading...</p>}

        {habitsQuery.isError && (
          <div className="notice">
            Couldn't load your habits just now.{" "}
            <button className="link" onClick={() => habitsQuery.refetch()}>
              Try again
            </button>
          </div>
        )}

        {habitsQuery.data && habits.length === 0 && <p className="empty-state">No habits yet.</p>}

        {habits.length > 0 && (
          <ul className="habit-list">
            {habits.map((habit) => (
              <HabitRow
                key={habit.id}
                habit={habit}
                linkedGoal={goals.find((g) => g.id === habit.goalId)}
                toggling={toggleMutation.isPending && toggleMutation.variables?.id === habit.id}
                saving={updateMutation.isPending && updateMutation.variables?.id === habit.id}
                onToggle={() => toggleMutation.mutate(habit)}
                onCommitLabel={(newLabel) => updateMutation.mutate({ id: habit.id, label: newLabel })}
                onDelete={() => handleDeleteClick(habit)}
              />
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
