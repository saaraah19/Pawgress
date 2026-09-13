import { useEffect, useMemo, useRef, useState, type FormEvent } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useAuth } from "../auth/AuthContext";
import { createJournalEntry, listJournalEntries, updateJournalEntry, deleteJournalEntry } from "../../api/client";
import { useToast } from "../../shared/ui/ToastProvider";
import { JOURNAL_QUERY_KEY } from "../../shared/queryKeys";
import type { JournalEntry } from "../../shared/types";

const UNDO_WINDOW_MS = 5000;

/** Grouping is by the entry's own local calendar day — deliberately NOT
 * the UTC-day convention used elsewhere (e.g. Habits) — a journal entry
 * written at 11pm should read as "today" to the person who wrote it, not
 * flip to the next day because a server clock is in UTC. This is pure
 * display grouping of an already-fetched timestamp; nothing here is a
 * durable concept the backend needs to agree on. */
function dayKeyOf(iso: string): string {
  const d = new Date(iso);
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

function dayHeadingLabel(iso: string): string {
  return new Date(iso).toLocaleDateString(undefined, { weekday: "long", month: "long", day: "numeric", year: "numeric" });
}

function dayChipLabel(iso: string): string {
  return new Date(iso).toLocaleDateString(undefined, { month: "short", day: "numeric" });
}

function timeLabel(iso: string): string {
  return new Date(iso).toLocaleTimeString(undefined, { hour: "numeric", minute: "2-digit" });
}

interface DayGroup {
  dayKey: string;
  entries: JournalEntry[];
}

/** Entries arrive already sorted desc by createdAt (backend's
 * list_journal_entries ordering) — grouping consecutive same-day entries
 * preserves that order rather than re-sorting. */
function groupByDay(entries: JournalEntry[]): DayGroup[] {
  const groups: DayGroup[] = [];
  for (const entry of entries) {
    const key = dayKeyOf(entry.createdAt);
    const last = groups[groups.length - 1];
    if (last && last.dayKey === key) {
      last.entries.push(entry);
    } else {
      groups.push({ dayKey: key, entries: [entry] });
    }
  }
  return groups;
}

/**
 * V2 Journal (Blueprint §13, Domain Model §13) — a distinct capture
 * surface, deliberately NOT built as an extension of the AI Inbox.
 * Nothing typed here is ever sent through extraction; this page never
 * calls createCapture. Plain writing in, plain writing back, nothing else.
 *
 * Day-grouped with a day filter (2026-09-13, owner's explicit request) —
 * replaces one long undifferentiated scroll of entries with a heading per
 * calendar day plus a row of day chips to jump straight to one day,
 * which stays usable as entry count grows rather than degrading into
 * endless scrolling. No backend change needed: entries are already
 * fetched in full and grouping/filtering happens client-side.
 *
 * No streak/frequency signal of any kind (generalizing FR-6.2's
 * no-absence-shaming principle beyond just the companion) — day chips are
 * a navigation aid, not a completion tracker; a day with zero entries
 * simply doesn't appear as a chip, no "you skipped this day" framing.
 */
export function JournalPage() {
  const { token } = useAuth();
  const queryClient = useQueryClient();
  const { showToast } = useToast();

  const [draft, setDraft] = useState("");
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editText, setEditText] = useState("");
  const [pendingDeleteIds, setPendingDeleteIds] = useState<Set<string>>(new Set());
  const [selectedDay, setSelectedDay] = useState<string | null>(null);
  const deleteTimers = useRef<Map<string, ReturnType<typeof setTimeout>>>(new Map());

  const entriesQuery = useQuery({
    queryKey: JOURNAL_QUERY_KEY,
    queryFn: () => listJournalEntries(token!),
    enabled: !!token,
  });

  const createMutation = useMutation({
    mutationFn: () => createJournalEntry({ text: draft.trim() }, token!),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: JOURNAL_QUERY_KEY });
      setDraft("");
      setSelectedDay(null); // a fresh entry should be visible immediately, not hidden behind an old filter
    },
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, text }: { id: string; text: string }) => updateJournalEntry(id, { text }, token!),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: JOURNAL_QUERY_KEY });
      setEditingId(null);
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => deleteJournalEntry(id, token!),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: JOURNAL_QUERY_KEY });
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
    if (!draft.trim() || createMutation.isPending) return;
    createMutation.mutate();
  }

  function startEditing(entry: JournalEntry) {
    setEditingId(entry.id);
    setEditText(entry.text);
  }

  function saveEdit(id: string) {
    const trimmed = editText.trim();
    if (!trimmed) return;
    updateMutation.mutate({ id, text: trimmed });
  }

  function handleDeleteClick(entry: JournalEntry) {
    setPendingDeleteIds((prev) => new Set(prev).add(entry.id));

    const timer = setTimeout(() => {
      deleteMutation.mutate(entry.id);
      deleteTimers.current.delete(entry.id);
      setPendingDeleteIds((prev) => {
        const next = new Set(prev);
        next.delete(entry.id);
        return next;
      });
    }, UNDO_WINDOW_MS);
    deleteTimers.current.set(entry.id, timer);

    showToast({
      message: "Entry deleted",
      actionLabel: "Undo",
      durationMs: UNDO_WINDOW_MS,
      onAction: () => {
        const pendingTimer = deleteTimers.current.get(entry.id);
        if (pendingTimer) {
          clearTimeout(pendingTimer);
          deleteTimers.current.delete(entry.id);
        }
        setPendingDeleteIds((prev) => {
          const next = new Set(prev);
          next.delete(entry.id);
          return next;
        });
      },
    });
  }

  const visibleEntries = (entriesQuery.data ?? []).filter((e) => !pendingDeleteIds.has(e.id));
  const allGroups = useMemo(() => groupByDay(visibleEntries), [visibleEntries]);
  const displayedGroups = selectedDay ? allGroups.filter((g) => g.dayKey === selectedDay) : allGroups;

  return (
    <div className="page journal-page">
      <div className="capture-card">
        <h1>Journal</h1>

        <form onSubmit={handleSubmit} className="capture-form">
          <textarea
            className="capture-textarea"
            placeholder="Write whatever's on your mind."
            aria-label="New journal entry"
            value={draft}
            disabled={createMutation.isPending}
            onChange={(e) => setDraft(e.target.value)}
            rows={4}
          />
          <button className="primary" type="submit" disabled={createMutation.isPending || !draft.trim()}>
            {createMutation.isPending ? "Saving..." : "Save entry"}
          </button>
        </form>

        {createMutation.isError && (
          <div className="notice">Couldn't save that just now. Nothing you wrote was lost — try again.</div>
        )}
      </div>

      <div className="journal-entries-section">
        {entriesQuery.isLoading && <p className="muted">Loading entries...</p>}

        {entriesQuery.isError && (
          <div className="notice">
            Couldn't load your entries just now.{" "}
            <button className="link" onClick={() => entriesQuery.refetch()}>
              Try again
            </button>
          </div>
        )}

        {entriesQuery.data && visibleEntries.length === 0 && (
          <p className="empty-state">Nothing written yet.</p>
        )}

        {allGroups.length > 1 && (
          <div className="journal-day-filter" role="group" aria-label="Filter entries by day">
            <button
              type="button"
              className={`journal-day-chip${selectedDay === null ? " is-active" : ""}`}
              onClick={() => setSelectedDay(null)}
            >
              All
            </button>
            {allGroups.map((group) => (
              <button
                key={group.dayKey}
                type="button"
                className={`journal-day-chip${selectedDay === group.dayKey ? " is-active" : ""}`}
                aria-pressed={selectedDay === group.dayKey}
                onClick={() => setSelectedDay(group.dayKey === selectedDay ? null : group.dayKey)}
              >
                {dayChipLabel(group.entries[0].createdAt)} ({group.entries.length})
              </button>
            ))}
          </div>
        )}

        {displayedGroups.map((group) => (
          <section key={group.dayKey} className="journal-day-group" aria-label={dayHeadingLabel(group.entries[0].createdAt)}>
            <h2 className="journal-day-heading">{dayHeadingLabel(group.entries[0].createdAt)}</h2>
            <ul className="journal-entry-list">
              {group.entries.map((entry) => (
                <li key={entry.id} className="journal-entry">
                  {editingId === entry.id ? (
                    <div className="journal-entry-editing">
                      <textarea
                        className="capture-textarea"
                        value={editText}
                        autoFocus
                        rows={4}
                        onChange={(e) => setEditText(e.target.value)}
                      />
                      <div className="journal-entry-edit-actions">
                        <button
                          type="button"
                          className="primary"
                          disabled={updateMutation.isPending || !editText.trim()}
                          onClick={() => saveEdit(entry.id)}
                        >
                          Save
                        </button>
                        <button type="button" className="link" onClick={() => setEditingId(null)}>
                          Cancel
                        </button>
                      </div>
                    </div>
                  ) : (
                    <>
                      <p className="journal-entry-time">{timeLabel(entry.createdAt)}</p>
                      <p className="journal-entry-text">{entry.text}</p>
                      <div className="journal-entry-actions">
                        <button type="button" className="link" onClick={() => startEditing(entry)}>
                          Edit
                        </button>
                        <button
                          type="button"
                          className="link task-delete"
                          onClick={() => handleDeleteClick(entry)}
                          aria-label="Delete this entry"
                        >
                          Delete
                        </button>
                      </div>
                    </>
                  )}
                </li>
              ))}
            </ul>
          </section>
        ))}
      </div>
    </div>
  );
}
