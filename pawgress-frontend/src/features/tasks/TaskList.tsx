import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useAuth } from "../auth/AuthContext";
import { listTasks, updateTask } from "../../api/client";
import { TaskRow } from "./TaskRow";
import type { Task, TaskUpdateRequest } from "../../shared/types";

export const TASKS_QUERY_KEY = ["tasks"] as const;

/**
 * FR-3.1: flat list, no nesting. System Architecture §5: server state is
 * the source of truth, fetched/cached via TanStack Query rather than
 * duplicated into local component state — this is what guarantees a
 * correction that appears to save actually did, since the displayed value
 * always comes from the last confirmed server response, never an
 * assumption.
 */
export function TaskList() {
  const { token } = useAuth();
  const queryClient = useQueryClient();

  const tasksQuery = useQuery({
    queryKey: TASKS_QUERY_KEY,
    queryFn: () => listTasks(token!),
    enabled: !!token,
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, patch }: { id: string; patch: TaskUpdateRequest }) =>
      updateTask(id, patch, token!),
    onSuccess: (updatedTask) => {
      // Reflect the server's confirmed response directly into the cache —
      // no optimistic guess, no separate refetch round trip either.
      queryClient.setQueryData<Task[]>(TASKS_QUERY_KEY, (old) =>
        old ? old.map((t) => (t.id === updatedTask.id ? updatedTask : t)) : old
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

  const tasks = tasksQuery.data ?? [];

  if (tasks.length === 0) {
    return <p className="muted">No tasks yet.</p>;
  }

  return (
    <ul className="task-list task-list-editable">
      {tasks.map((task) => (
        <TaskRow
          key={task.id}
          task={task}
          saving={updateMutation.isPending && updateMutation.variables?.id === task.id}
          onCommit={(patch) => updateMutation.mutate({ id: task.id, patch })}
        />
      ))}
    </ul>
  );
}
