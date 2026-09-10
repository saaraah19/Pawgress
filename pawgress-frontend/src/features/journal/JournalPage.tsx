import { useEffect, useRef, useState, type FormEvent } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useAuth } from "../auth/AuthContext";
import { createJournalEntry, listJournalEntries, updateJournalEntry, deleteJournalEntry } from "../../api/client";
import { useToast } from "../../shared/ui/ToastProvider";
import { JOURNAL_QUERY_KEY } from "../../shared/queryKeys";
import type { JournalEntry } from "../../shared/types";

const UNDO_WINDOW_MS = 5000;

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" });
}

/**
 * V2 Journal (Blueprint §13, Domain Model §13) — a distinct capture
 * surface, deliberately NOT built as an extension of the AI Inbox.
 * Nothing typed here is ever sent through extraction; this page never
 * calls createCapture. Plain writing in, plain writing back, nothing else.
 *
 * No streak/frequency signal of any kind (generalizing FR-6.2's
 * no-absence-shaming principle beyond just the companion) — the empty
 * state and the page as a whole never mention how long it's been since
 * the last entry.
 */
export function JournalPage() {
  const { token } = useAuth();
  const queryClient = useQueryClient();
  const { showToast } = useToast();

  const [draft, setDraft] = useState("");
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editText, setEditText] = useState("");
  const [pendingDeleteIds, setPendingDeleteIds] = useState<Set<string>>(new Set());
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

        {visibleEntries.length > 0 && (
          <ul className="journal-entry-list">
            {visibleEntries.map((entry) => (
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
                    <p className="journal-entry-date">{formatDate(entry.createdAt)}</p>
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
        )}
      </div>
    </div>
  );
}
