import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useAuth } from "../auth/AuthContext";
import { listTasks, updateTask, deleteTask, listGoals } from "../../api/client";
import { TaskRow } from "./TaskRow";
import { ManualTaskForm } from "./ManualTaskForm";
import { TASKS_QUERY_KEY, GOALS_QUERY_KEY } from "../../shared/queryKeys";
import type { Task, TaskUpdateRequest } from "../../shared/types";

type ViewMode = "today" | "all";

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
  const [view, setView] = useState<ViewMode>("today");

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
  const visibleTasks = view === "today" ? allTasks.filter((t) => t.status === "NotStarted") : allTasks;

  return (
    <div>
      <nav className="view-toggle">
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
        <p className="empty-state">
          {view === "today" ? "Nothing on your plate right now." : "No tasks yet."}
        </p>
      ) : (
        <ul className="task-list task-list-editable">
          {visibleTasks.map((task) => (
            <TaskRow
              key={task.id}
              task={task}
              goals={goals}
              saving={updateMutation.isPending && updateMutation.variables?.id === task.id}
              deleting={deleteMutation.isPending && deleteMutation.variables === task.id}
              onCommit={(patch) => updateMutation.mutate({ id: task.id, patch })}
              onDelete={() => deleteMutation.mutate(task.id)}
            />
          ))}
        </ul>
      )}
    </div>
  );
}