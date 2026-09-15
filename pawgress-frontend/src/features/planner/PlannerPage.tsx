import { useEffect, useMemo, useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useAuth } from "../auth/AuthContext";
import { getPlannerEntry, upsertPlannerEntry } from "../../api/client";
import { PLANNER_QUERY_KEY } from "../../shared/queryKeys";
import type { PlannerPeriodType } from "../../shared/types";

function todayUtcIso(): string {
  return new Date().toISOString().slice(0, 10);
}

function addDaysIso(iso: string, days: number): string {
  const [y, m, d] = iso.split("-").map(Number);
  const dt = new Date(Date.UTC(y, m - 1, d));
  dt.setUTCDate(dt.getUTCDate() + days);
  return dt.toISOString().slice(0, 10);
}

function addMonthsIso(iso: string, months: number): string {
  const [y, m, d] = iso.split("-").map(Number);
  const dt = new Date(Date.UTC(y, m - 1, d));
  dt.setUTCMonth(dt.getUTCMonth() + months);
  return dt.toISOString().slice(0, 10);
}

/** Sunday-start week containing today — same convention as HabitsPage.tsx,
 * so the two features never disagree about what "this week" means. */
function currentWeekStartIso(): string {
  const today = todayUtcIso();
  const [y, m, d] = today.split("-").map(Number);
  const dt = new Date(Date.UTC(y, m - 1, d));
  dt.setUTCDate(dt.getUTCDate() - dt.getUTCDay());
  return dt.toISOString().slice(0, 10);
}

function currentMonthStartIso(): string {
  const today = todayUtcIso();
  return `${today.slice(0, 7)}-01`;
}

function weekRangeLabel(weekStart: string): string {
  const weekEnd = addDaysIso(weekStart, 6);
  const fmt = (iso: string) =>
    new Date(`${iso}T00:00:00Z`).toLocaleDateString(undefined, { month: "short", day: "numeric", timeZone: "UTC" });
  return `${fmt(weekStart)} – ${fmt(weekEnd)}`;
}

function monthLabel(monthStart: string): string {
  return new Date(`${monthStart}T00:00:00Z`).toLocaleDateString(undefined, {
    month: "long",
    year: "numeric",
    timeZone: "UTC",
  });
}

/**
 * Weekly/Monthly Planner (2026-09-15) — Sarah's explicit design: set an
 * intention at the start of a week/month, write a reflection whenever you
 * get to it. Deliberately independent of the Goal hierarchy (no linking)
 * and deliberately NOT timing-gated — both fields are always editable
 * regardless of where you are in the period, matching the product's
 * broader "don't impose manual system maintenance" philosophy.
 *
 * No completion tracking of "did you fill this in" for the same reason
 * Habits/Journal don't shame absence — a period with nothing written in
 * it is just a period with nothing written in it.
 */
export function PlannerPage() {
  const { token } = useAuth();
  const queryClient = useQueryClient();

  const [periodType, setPeriodType] = useState<PlannerPeriodType>("Week");
  const [weekStart, setWeekStart] = useState(currentWeekStartIso());
  const [monthStart, setMonthStart] = useState(currentMonthStartIso());

  const periodStart = periodType === "Week" ? weekStart : monthStart;
  const isCurrentPeriod =
    periodType === "Week" ? weekStart === currentWeekStartIso() : monthStart === currentMonthStartIso();

  const entryQuery = useQuery({
    queryKey: [...PLANNER_QUERY_KEY, periodType, periodStart],
    queryFn: () => getPlannerEntry(periodType, periodStart, token!),
    enabled: !!token,
  });

  const [intention, setIntention] = useState("");
  const [reflection, setReflection] = useState("");

  useEffect(() => {
    setIntention(entryQuery.data?.intention ?? "");
    setReflection(entryQuery.data?.reflection ?? "");
  }, [entryQuery.data, periodType, periodStart]);

  const saveMutation = useMutation({
    mutationFn: (patch: { intention?: string; reflection?: string }) =>
      upsertPlannerEntry({ periodType, periodStart, ...patch }, token!),
    onSuccess: (entry) => {
      queryClient.setQueryData([...PLANNER_QUERY_KEY, periodType, periodStart], entry);
    },
  });

  function commitIntention() {
    if (intention !== (entryQuery.data?.intention ?? "")) {
      saveMutation.mutate({ intention });
    }
  }

  function commitReflection() {
    if (reflection !== (entryQuery.data?.reflection ?? "")) {
      saveMutation.mutate({ reflection });
    }
  }

  const periodLabel = useMemo(
    () => (periodType === "Week" ? weekRangeLabel(weekStart) : monthLabel(monthStart)),
    [periodType, weekStart, monthStart]
  );

  function goToPrevious() {
    if (periodType === "Week") setWeekStart((w) => addDaysIso(w, -7));
    else setMonthStart((m) => addMonthsIso(m, -1));
  }

  function goToNext() {
    if (periodType === "Week") setWeekStart((w) => addDaysIso(w, 7));
    else setMonthStart((m) => addMonthsIso(m, 1));
  }

  function goToCurrent() {
    if (periodType === "Week") setWeekStart(currentWeekStartIso());
    else setMonthStart(currentMonthStartIso());
  }

  return (
    <div className="page">
      <div className="card planner-card">
        <h1>Planner</h1>

        <nav className="view-toggle" role="group" aria-label="Planning period">
          <button
            type="button"
            className="link"
            aria-current={periodType === "Week"}
            onClick={() => setPeriodType("Week")}
          >
            Week
          </button>
          <button
            type="button"
            className="link"
            aria-current={periodType === "Month"}
            onClick={() => setPeriodType("Month")}
          >
            Month
          </button>
        </nav>

        <div className="planner-period-nav">
          <button type="button" className="link" onClick={goToPrevious} aria-label={`Previous ${periodType.toLowerCase()}`}>
            ←
          </button>
          <span className="planner-period-label">
            {periodLabel}
            {!isCurrentPeriod && (
              <button type="button" className="link" onClick={goToCurrent}>
                {periodType === "Week" ? "This week" : "This month"}
              </button>
            )}
          </span>
          <button type="button" className="link" onClick={goToNext} aria-label={`Next ${periodType.toLowerCase()}`}>
            →
          </button>
        </div>

        {entryQuery.isLoading && <p className="muted">Loading...</p>}

        {entryQuery.isError && (
          <div className="notice">
            Couldn't load this just now.{" "}
            <button className="link" onClick={() => entryQuery.refetch()}>
              Try again
            </button>
          </div>
        )}

        {!entryQuery.isLoading && (
          <>
            <div className="field planner-field">
              <label htmlFor="planner-intention">
                {periodType === "Week" ? "What are you focusing on this week?" : "What are you focusing on this month?"}
              </label>
              <textarea
                id="planner-intention"
                className="capture-textarea"
                rows={3}
                value={intention}
                disabled={saveMutation.isPending}
                onChange={(e) => setIntention(e.target.value)}
                onBlur={commitIntention}
              />
            </div>

            <div className="field planner-field">
              <label htmlFor="planner-reflection">Reflection</label>
              <textarea
                id="planner-reflection"
                className="capture-textarea"
                placeholder="Whenever you're ready — no rush."
                rows={3}
                value={reflection}
                disabled={saveMutation.isPending}
                onChange={(e) => setReflection(e.target.value)}
                onBlur={commitReflection}
              />
            </div>
          </>
        )}
      </div>
    </div>
  );
}
