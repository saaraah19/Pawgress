import { useState, useEffect } from "react";
import type { Task, TaskUpdateRequest, Priority, Goal } from "../../shared/types";

interface TaskRowProps {
  task: Task;
  goals: Goal[];
  onCommit: (patch: TaskUpdateRequest) => void;
  onDelete: () => void;
  saving: boolean;
  deleting: boolean;
}

const PRIORITIES: Priority[] = ["Low", "Medium", "High"];

export function TaskRow({ task, goals, onCommit, onDelete, saving, deleting }: TaskRowProps) {
  const [title, setTitle] = useState(task.title);
  const [category, setCategory] = useState(task.category ?? "");
  const [estimateText, setEstimateText] = useState(
    task.estimateMinutes !== null ? String(task.estimateMinutes) : ""
  );
  const [linking, setLinking] = useState(false);

  useEffect(() => {
    setTitle(task.title);
  }, [task.title]);
  useEffect(() => {
    setCategory(task.category ?? "");
  }, [task.category]);
  useEffect(() => {
    setEstimateText(task.estimateMinutes !== null ? String(task.estimateMinutes) : "");
  }, [task.estimateMinutes]);

  function commitTitle() {
    const trimmed = title.trim();
    if (trimmed && trimmed !== task.title) {
      onCommit({ title: trimmed });
    } else {
      setTitle(task.title);
    }
  }

  function commitCategory() {
    const trimmed = category.trim();
    if (trimmed && trimmed !== (task.category ?? "")) {
      onCommit({ category: trimmed });
    } else {
      setCategory(task.category ?? "");
    }
  }

  function commitPriority(next: Priority) {
    if (next !== task.priority) {
      onCommit({ priority: next });
    }
  }

  function commitEstimate() {
    const trimmed = estimateText.trim();
    const parsed = trimmed === "" ? null : Number(trimmed);
    const validParsed = parsed !== null && Number.isFinite(parsed) && parsed > 0 ? Math.round(parsed) : null;
    if (validParsed !== task.estimateMinutes) {
      onCommit({ estimateMinutes: validParsed });
    }
    setEstimateText(validParsed !== null ? String(validParsed) : "");
  }

  function toggleStatus() {
    onCommit({ status: task.status === "Done" ? "NotStarted" : "Done" });
  }

  const linkedGoal = goals.find((g) => g.id === task.goalId) ?? null;
  const disabled = saving || deleting;

  return (
    <li className={`task-row task-row-editable ${task.status === "Done" ? "task-row-done" : ""}`}>
      <input
        type="checkbox"
        className="task-status-checkbox"
        checked={task.status === "Done"}
        disabled={disabled}
        onChange={toggleStatus}
        aria-label={task.status === "Done" ? "Mark as not started" : "Mark as done"}
      />

      <input
        className={`field-inline field-title ${task.status === "Done" ? "field-title-done" : ""}`}
        value={title}
        disabled={disabled}
        onChange={(e) => setTitle(e.target.value)}
        onBlur={commitTitle}
        onKeyDown={(e) => e.key === "Enter" && (e.target as HTMLInputElement).blur()}
      />

      <input
        className="field-inline field-category"
        value={category}
        placeholder="—"
        disabled={disabled}
        onChange={(e) => setCategory(e.target.value)}
        onBlur={commitCategory}
        onKeyDown={(e) => e.key === "Enter" && (e.target as HTMLInputElement).blur()}
      />

      <select
        className="field-inline field-priority"
        value={task.priority}
        disabled={disabled}
        onChange={(e) => commitPriority(e.target.value as Priority)}
      >
        {PRIORITIES.map((p) => (
          <option key={p} value={p}>
            {p}
          </option>
        ))}
      </select>

      <span className="field-estimate-group">
        <input
          className="field-inline field-estimate"
          type="text"
          inputMode="numeric"
          placeholder="—"
          value={estimateText}
          disabled={disabled}
          onChange={(e) => setEstimateText(e.target.value)}
          onBlur={commitEstimate}
          onKeyDown={(e) => e.key === "Enter" && (e.target as HTMLInputElement).blur()}
        />
        <span className="field-estimate-unit">min</span>
      </span>

      {goals.length > 0 && (
        <span className="field-goal-group">
          {linkedGoal ? (
            <button type="button" className="link" disabled={disabled} onClick={() => onCommit({ goalId: null })}>
              {linkedGoal.label} ✕
            </button>
          ) : linking ? (
            <span className="goal-picker">
              {goals.map((g) => (
                <button
                  key={g.id}
                  type="button"
                  className="link"
                  onClick={() => {
                    onCommit({ goalId: g.id });
                    setLinking(false);
                  }}
                >
                  {g.label}
                </button>
              ))}
              <button type="button" className="link" onClick={() => setLinking(false)}>
                Cancel
              </button>
            </span>
          ) : (
            <button type="button" className="link" disabled={disabled} onClick={() => setLinking(true)}>
              Link to goal
            </button>
          )}
        </span>
      )}

      <button
        type="button"
        className="link task-delete"
        disabled={disabled}
        onClick={onDelete}
        aria-label={`Delete "${task.title}"`}
      >
        Delete
      </button>
    </li>
  );
}