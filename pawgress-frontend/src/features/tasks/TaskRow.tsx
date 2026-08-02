import { useState, useEffect } from "react";
import type { Task, TaskUpdateRequest, Priority } from "../../shared/types";

interface TaskRowProps {
  task: Task;
  onCommit: (patch: TaskUpdateRequest) => void;
  saving: boolean;
}

const PRIORITIES: Priority[] = ["Low", "Medium", "High"];

/**
 * The Quiet Correction (UX Philosophy §5.2), field by field, plus the
 * Completing and Reflecting interaction (UX Philosophy §5.3) for status:
 * - FR-4.1: fixed in place, no separate edit screen.
 * - FR-4.2: no confirmation step — commits directly on blur/change.
 * - FR-4.3: no reactive/apologetic copy on save, ever.
 * - FR-3.3: status is directly editable too — but a status toggle is
 *   intentionally NOT treated as a "correction" (no FieldCorrectionRecord,
 *   per the backend's own CORRECTION_TRACKED_FIELDS guard) and gets no
 *   acknowledgment copy beyond the checkbox itself changing — ordinary
 *   completions are quiet, per §5.3's "a checkbox state change is often
 *   enough."
 *
 * Each field sends only its own value on commit (e.g. {title: "..."}), not
 * the whole row — keeps a correction a single, atomic action per field
 * rather than a bundled form submission.
 */
export function TaskRow({ task, onCommit, saving }: TaskRowProps) {
  const [title, setTitle] = useState(task.title);
  const [category, setCategory] = useState(task.category);
  const [estimateText, setEstimateText] = useState(
    task.estimateMinutes !== null ? String(task.estimateMinutes) : ""
  );

  // Only resync local drafts when the task's OWN committed values change
  // (e.g. after this row's own successful correction, or a fresh fetch) —
  // not on every parent re-render, so an in-progress edit in another field
  // isn't clobbered mid-keystroke.
  useEffect(() => {
    setTitle(task.title);
  }, [task.title]);
  useEffect(() => {
    setCategory(task.category);
  }, [task.category]);
  useEffect(() => {
    setEstimateText(task.estimateMinutes !== null ? String(task.estimateMinutes) : "");
  }, [task.estimateMinutes]);

  function commitTitle() {
    const trimmed = title.trim();
    if (trimmed && trimmed !== task.title) {
      onCommit({ title: trimmed });
    } else {
      setTitle(task.title); // revert an emptied/unchanged draft, no error shown
    }
  }

  function commitCategory() {
    const trimmed = category.trim();
    if (trimmed && trimmed !== task.category) {
      onCommit({ category: trimmed });
    } else {
      setCategory(task.category);
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
    // Reflect whatever we actually resolved to (e.g. invalid input reverts).
    setEstimateText(validParsed !== null ? String(validParsed) : "");
  }

  function toggleStatus() {
    onCommit({ status: task.status === "Done" ? "NotStarted" : "Done" });
  }

  return (
    <li className={`task-row task-row-editable ${task.status === "Done" ? "task-row-done" : ""}`}>
      <input
        type="checkbox"
        className="task-status-checkbox"
        checked={task.status === "Done"}
        disabled={saving}
        onChange={toggleStatus}
        aria-label={task.status === "Done" ? "Mark as not started" : "Mark as done"}
      />

      <input
        className={`field-inline field-title ${task.status === "Done" ? "field-title-done" : ""}`}
        value={title}
        disabled={saving}
        onChange={(e) => setTitle(e.target.value)}
        onBlur={commitTitle}
        onKeyDown={(e) => e.key === "Enter" && (e.target as HTMLInputElement).blur()}
      />

      <input
        className="field-inline field-category"
        value={category}
        disabled={saving}
        onChange={(e) => setCategory(e.target.value)}
        onBlur={commitCategory}
        onKeyDown={(e) => e.key === "Enter" && (e.target as HTMLInputElement).blur()}
      />

      <select
        className="field-inline field-priority"
        value={task.priority}
        disabled={saving}
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
          disabled={saving}
          onChange={(e) => setEstimateText(e.target.value)}
          onBlur={commitEstimate}
          onKeyDown={(e) => e.key === "Enter" && (e.target as HTMLInputElement).blur()}
        />
        <span className="field-estimate-unit">min</span>
      </span>
    </li>
  );
}
