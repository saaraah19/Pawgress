import { useEffect, useRef, useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useAuth } from "../auth/AuthContext";
import { listTasks, updateTask, deleteTask, listGoals } from "../../api/client";
import { TaskRow } from "./TaskRow";
import { ManualTaskForm } from "./ManualTaskForm";
import { useToast } from "../../shared/ui/ToastProvider";
import { EmptyState } from "../../shared/ui/EmptyState";
import { TASKS_QUERY_KEY, GOALS_QUERY_KEY } from "../../shared/queryKeys";
import type { Task, TaskUpdateRequest } from "../../shared/types";

type ViewMode = "today" | "all";

// How long a deleted task stays reversible before the delete actually
// commits to the server. Matches the toast's own auto-dismiss window
// (shared/ui/ToastProvider.tsx's DEFAULT_DURATION_MS) so the toast
// disappearing and the delete becoming permanent happen at the same
// moment — a toast that outlives its own undo window (or vice versa)
// would be a confusing, incoherent bit of feedback.
const UNDO_WINDOW_MS = 5000;

/**
 * FR-3.1 ("all active tasks") and FR-7.1 ("today's incomplete tasks") are
 * both served from the same GET /tasks response, filtered client-side —
 * task volume at MVP scale doesn't justify a server-side filter param.
 * "Today" (incomplete only) is the default view; "All Tasks" is one tap
 * away and includes completed tasks. No due-date/absence logic anywhere
 * (BR-7) — there's nothing to compute, so nothing to accidentally show.
 */
export function TaskList() {
  const { token } = useAuth();
  const queryClient = useQueryClient();
  const { showToast } = useToast();
  const [view, setView] = useState<ViewMode>("today");

  // Delete-with-undo (polish slice item 3): clicking Delete hides the row
  // immediately and starts a grace-window timer, rather than either (a)
  // deleting for real with no way back, or (b) a confirmation dialog,
  // which AC-3.5.1 explicitly rules out. Nothing is sent to the server
  // until the window elapses without an Undo.
  const [pendingDeleteIds, setPendingDeleteIds] = useState<Set<string>>(new Set());
  const deleteTimers = useRef<Map<string, ReturnType<typeof setTimeout>>>(new Map());

  const tasksQuery = useQuery({
    queryKey: TASKS_QUERY_KEY,
    queryFn: () => listTasks(token!),
    enabled: !!token,
  });

  const goalsQuery = useQuery({
    queryKey: GOALS_QUERY_KEY,
    queryFn: () => listGoals(token!),
    enabled: !!token,
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, patch }: { id: string; patch: TaskUpdateRequest }) =>
      updateTask(id, patch, token!),
    onSuccess: (updatedTask) => {
      queryClient.setQueryData<Task[]>(TASKS_QUERY_KEY, (old) =>
        old ? old.map((t) => (t.id === updatedTask.id ? updatedTask : t)) : old
      );
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => deleteTask(id, token!),
    onSuccess: (_data, deletedId) => {
      queryClient.setQueryData<Task[]>(TASKS_QUERY_KEY, (old) =>
        old ? old.filter((t) => t.id !== deletedId) : old
      );
    },
  });

  // If the user navigates away mid-undo-window, honor the delete they
  // already asked for rather than silently discarding it — the row is
  // gone from their screen either way, so leaving it undeleted on the
  // server would be a quiet, confusing inconsistency the next time they
  // load the list. Calls the mutation directly rather than going through
  // React state, since this runs during unmount.
  useEffect(() => {
    return () => {
      deleteTimers.current.forEach((timer, id) => {
        clearTimeout(timer);
        deleteMutation.mutate(id);
      });
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function handleDeleteClick(task: Task) {
    setPendingDeleteIds((prev) => new Set(prev).add(task.id));

    const timer = setTimeout(() => {
      deleteMutation.mutate(task.id);
      deleteTimers.current.delete(task.id);
      setPendingDeleteIds((prev) => {
        const next = new Set(prev);
        next.delete(task.id);
        return next;
      });
    }, UNDO_WINDOW_MS);
    deleteTimers.current.set(task.id, timer);

    showToast({
      message: `"${task.title}" deleted`,
      actionLabel: "Undo",
      durationMs: UNDO_WINDOW_MS,
      onAction: () => {
        const pendingTimer = deleteTimers.current.get(task.id);
        if (pendingTimer) {
          clearTimeout(pendingTimer);
          deleteTimers.current.delete(task.id);
        }
        setPendingDeleteIds((prev) => {
          const next = new Set(prev);
          next.delete(task.id);
          return next;
        });
      },
    });
  }

  if (tasksQuery.isLoading) {
    return <p className="muted">Loading tasks...</p>;
  }

  if (tasksQuery.isError) {
    return (
      <div className="notice">
        Couldn't load your tasks just now.{" "}
        <button className="link" onClick={() => tasksQuery.refetch()}>
          Try again
        </button>
      </div>
    );
  }

  const allTasks = tasksQuery.data ?? [];
  const goals = goalsQuery.data ?? [];
  const visibleTasks = (view === "today" ? allTasks.filter((t) => t.status === "NotStarted") : allTasks).filter(
    (t) => !pendingDeleteIds.has(t.id)
  );

  return (
    <div>
      <nav className="view-toggle" role="group" aria-label="Task view">
        <button
          type="button"
          className="link"
          aria-current={view === "today"}
          onClick={() => setView("today")}
        >
          Today
        </button>
        <button
          type="button"
          className="link"
          aria-current={view === "all"}
          onClick={() => setView("all")}
        >
          All Tasks
        </button>
      </nav>

      <ManualTaskForm />

      {visibleTasks.length === 0 ? (
        <EmptyState
          mood="resting"
          message={
            view === "today"
              ? "Nothing's waiting. The cat's dozing too."
              : "No tasks yet. The cat's dozing too."
          }
        />
      ) : (
        <ul className="task-list task-list-editable">
          {visibleTasks.map((task) => (
            <TaskRow
              key={task.id}
              task={task}
              goals={goals}
              saving={updateMutation.isPending && updateMutation.variables?.id === task.id}
              onCommit={(patch) => updateMutation.mutate({ id: task.id, patch })}
              onDelete={() => handleDeleteClick(task)}
            />
          ))}
        </ul>
      )}
    </div>
  );
}
