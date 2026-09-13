import { useEffect, useMemo, useRef, useState, type FormEvent } from "react";
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
 * (habits/models.py) — every date used in this file is a plain UTC
 * calendar day, never a local-timezone one, so the week table lines up
 * with what the backend considers "today." */
function todayUtcIso(): string {
  return new Date().toISOString().slice(0, 10);
}

function addDaysIso(iso: string, days: number): string {
  const [y, m, d] = iso.split("-").map(Number);
  const dt = new Date(Date.UTC(y, m - 1, d));
  dt.setUTCDate(dt.getUTCDate() + days);
  return dt.toISOString().slice(0, 10);
}

/** Sunday-start week containing today, mirroring the backend's
 * `_week_start_of` in habits/routes.py exactly (Sunday chosen per Sarah's
 * call) — kept as a single source of truth here so every other date
 * calculation in this file derives from it. */
function currentWeekStartIso(): string {
  const today = todayUtcIso();
  const [y, m, d] = today.split("-").map(Number);
  const dt = new Date(Date.UTC(y, m - 1, d));
  dt.setUTCDate(dt.getUTCDate() - dt.getUTCDay()); // getUTCDay(): Sunday = 0
  return dt.toISOString().slice(0, 10);
}

function weekdayShortLabel(iso: string): string {
  return new Date(`${iso}T00:00:00Z`).toLocaleDateString(undefined, { weekday: "short", timeZone: "UTC" });
}

function dayNumberLabel(iso: string): string {
  return new Date(`${iso}T00:00:00Z`).toLocaleDateString(undefined, { day: "numeric", timeZone: "UTC" });
}

function weekRangeLabel(weekStart: string): string {
  const weekEnd = addDaysIso(weekStart, 6);
  const fmt = (iso: string) =>
    new Date(`${iso}T00:00:00Z`).toLocaleDateString(undefined, { month: "short", day: "numeric", timeZone: "UTC" });
  return `${fmt(weekStart)} – ${fmt(weekEnd)}`;
}

interface HabitTableRowProps {
  habit: Habit;
  linkedGoal: Goal | undefined;
  days: string[];
  today: string;
  onToggleDay: (dateIso: string) => void;
  onCommitLabel: (label: string) => void;
  onDelete: () => void;
  togglingDate: string | null;
  saving: boolean;
}

/** Same always-editable-input pattern as TaskRow.tsx: local state synced
 * from props, commits on blur if changed, no separate view/edit toggle. */
function HabitTableRow({
  habit,
  linkedGoal,
  days,
  today,
  onToggleDay,
  onCommitLabel,
  onDelete,
  togglingDate,
  saving,
}: HabitTableRowProps) {
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

  const weekCount = habit.completedDates.length;

  return (
    <tr className="habit-row-tr">
      <th scope="row" className="habit-name-cell">
        <input
          className="field-inline field-title"
          value={label}
          disabled={saving}
          onChange={(e) => setLabel(e.target.value)}
          onBlur={commit}
          onKeyDown={(e) => e.key === "Enter" && (e.target as HTMLInputElement).blur()}
        />
        <span className="habit-meta">
          {habit.frequency === "Daily" ? "Daily" : `${weekCount}/${habit.weeklyTarget} this week`}
          {" · "}
          done {habit.totalCompletions} {habit.totalCompletions === 1 ? "time" : "times"}
          {linkedGoal ? ` · ${linkedGoal.label}` : ""}
        </span>
        <button type="button" className="link task-delete" onClick={onDelete} aria-label={`Delete "${habit.label}"`}>
          Delete
        </button>
      </th>
      {days.map((dateIso) => {
        const done = habit.completedDates.includes(dateIso);
        const isFuture = dateIso > today;
        return (
          <td key={dateIso} className={dateIso === today ? "is-today" : undefined}>
            <button
              type="button"
              className={`habit-day-toggle${done ? " is-done" : ""}`}
              disabled={isFuture || togglingDate === dateIso}
              aria-pressed={done}
              aria-label={`${habit.label} — ${weekdayShortLabel(dateIso)} ${dayNumberLabel(dateIso)}${
                done ? ", done" : isFuture ? ", not yet due" : ", not done"
              }`}
              onClick={() => onToggleDay(dateIso)}
            >
              {done ? "✓" : ""}
            </button>
          </td>
        );
      })}
    </tr>
  );
}

/**
 * V2 Habits (Blueprint §13, §16), redesigned as a plain checklist table —
 * habit names as rows, days of the week as columns, checkable cells.
 * Deliberately shows NO streak counter — progress is a plain accumulating
 * total that never resets (see habits/models.py's docstring for the full
 * reasoning). No red, no "broken" language, no indication anywhere of a
 * missed day; empty cells are just unchecked, not colored as a warning.
 * Week navigation (back to any past week, forward as far as you like)
 * reuses the same completion endpoints — toggling a cell in any week is
 * just marking/unmarking that specific date; future days are disabled
 * since there's nothing to mark complete yet.
 */
export function HabitsPage() {
  const { token } = useAuth();
  const queryClient = useQueryClient();
  const { showToast } = useToast();

  const [weekStart, setWeekStart] = useState(currentWeekStartIso());
  const today = todayUtcIso();
  const days = useMemo(() => Array.from({ length: 7 }, (_, i) => addDaysIso(weekStart, i)), [weekStart]);

  const [label, setLabel] = useState("");
  const [frequency, setFrequency] = useState<HabitFrequency>("Daily");
  const [weeklyTarget, setWeeklyTarget] = useState("3");
  const [goalId, setGoalId] = useState("");
  const [formError, setFormError] = useState<string | null>(null);
  const [pendingDeleteIds, setPendingDeleteIds] = useState<Set<string>>(new Set());
  const deleteTimers = useRef<Map<string, ReturnType<typeof setTimeout>>>(new Map());

  const habitsQuery = useQuery({
    queryKey: [...HABITS_QUERY_KEY, weekStart],
    queryFn: () => listHabits(token!, weekStart),
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
        token!,
        weekStart
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
    mutationFn: ({ habit, dateIso }: { habit: Habit; dateIso: string }) =>
      habit.completedDates.includes(dateIso)
        ? unmarkHabitComplete(habit.id, dateIso, token!, weekStart)
        : markHabitComplete(habit.id, token!, dateIso, weekStart),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: HABITS_QUERY_KEY });
    },
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, label: newLabel }: { id: string; label: string }) =>
      updateHabit(id, { label: newLabel }, token!, weekStart),
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
  const togglingKey = toggleMutation.isPending ? toggleMutation.variables : undefined;

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

        <div className="habit-week-nav">
          <button
            type="button"
            className="link"
            onClick={() => setWeekStart((w) => addDaysIso(w, -7))}
            aria-label="Previous week"
          >
            ← Previous
          </button>
          <span className="habit-week-label">
            {weekRangeLabel(weekStart)}
            {weekStart !== currentWeekStartIso() && (
              <button type="button" className="link" onClick={() => setWeekStart(currentWeekStartIso())}>
                This week
              </button>
            )}
          </span>
          <button
            type="button"
            className="link"
            onClick={() => setWeekStart((w) => addDaysIso(w, 7))}
            aria-label="Next week"
          >
            Next →
          </button>
        </div>

        {habitsQuery.isLoading && <p className="muted">Loading habits...</p>}

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
          <div className="habit-table-wrap">
            <table className="habit-table">
              <thead>
                <tr>
                  <th scope="col" className="habit-name-cell">
                    Habit
                  </th>
                  {days.map((dateIso) => (
                    <th scope="col" key={dateIso} className={dateIso === today ? "is-today" : undefined}>
                      <span className="habit-day-weekday">{weekdayShortLabel(dateIso)}</span>
                      <span className="habit-day-number">{dayNumberLabel(dateIso)}</span>
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {habits.map((habit) => (
                  <HabitTableRow
                    key={habit.id}
                    habit={habit}
                    linkedGoal={goals.find((g) => g.id === habit.goalId)}
                    days={days}
                    today={today}
                    togglingDate={togglingKey?.habit.id === habit.id ? togglingKey.dateIso : null}
                    saving={updateMutation.isPending && updateMutation.variables?.id === habit.id}
                    onToggleDay={(dateIso) => toggleMutation.mutate({ habit, dateIso })}
                    onCommitLabel={(newLabel) => updateMutation.mutate({ id: habit.id, label: newLabel })}
                    onDelete={() => handleDeleteClick(habit)}
                  />
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
