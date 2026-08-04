import { useState, type FormEvent } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useAuth } from "../auth/AuthContext";
import { createTask } from "../../api/client";
import { TASKS_QUERY_KEY } from "../../shared/queryKeys";
import type { Priority } from "../../shared/types";

/**
 * FR-3.4 — direct task creation, bypassing the AI Inbox entirely ("AI-first
 * does not mean AI-only"). An ordinary interaction (UX Philosophy §6), not a
 * signature one: no ceremony, no celebratory copy on success (the same
 * restraint FR-2.5 requires of extraction applies here too — adding a task
 * isn't an achievement).
 *
 * Collapsed to a single title field by default. Per AC-3.4.1, category/
 * priority/estimate are optional and never inferred for a manually-created
 * task — most people just want to type a title, so the extra fields are
 * tucked behind "+ Add category, priority, or estimate" rather than shown
 * up front, matching the restraint principle in UX Philosophy §3 (friction
 * is evaluated by what it costs to be wrong, not step count — hiding
 * optional fields costs nothing since they can always be set later via the
 * Quiet Correction interaction).
 */
export function ManualTaskForm() {
  const { token } = useAuth();
  const queryClient = useQueryClient();
  const [open, setOpen] = useState(false);
  const [showDetails, setShowDetails] = useState(false);
  const [title, setTitle] = useState("");
  const [category, setCategory] = useState("");
  const [priority, setPriority] = useState<Priority>("Medium");
  const [estimate, setEstimate] = useState("");

  const createMutation = useMutation({
    mutationFn: () =>
      createTask(
        {
          title: title.trim(),
          category: category.trim() || undefined,
          priority,
          estimateMinutes: estimate.trim() ? Number(estimate) : undefined,
        },
        token!
      ),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: TASKS_QUERY_KEY });
      resetAndClose();
    },
  });

  function resetAndClose() {
    setTitle("");
    setCategory("");
    setPriority("Medium");
    setEstimate("");
    setShowDetails(false);
    setOpen(false);
  }

  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    const trimmed = title.trim();
    if (!trimmed) return;
    createMutation.mutate();
  }

  if (!open) {
    return (
      <button type="button" className="link add-task-toggle" onClick={() => setOpen(true)}>
        + Add a task
      </button>
    );
  }

  return (
    <form onSubmit={handleSubmit} className="manual-task-form">
      <div className="capture-form">
        <input
          className="field-inline"
          placeholder="What do you need to do?"
          value={title}
          autoFocus
          disabled={createMutation.isPending}
          onChange={(e) => setTitle(e.target.value)}
        />
        <button className="primary" type="submit" disabled={createMutation.isPending || !title.trim()}>
          Add
        </button>
        <button type="button" className="link" onClick={resetAndClose}>
          Cancel
        </button>
      </div>

      {!showDetails ? (
        <button
          type="button"
          className="link manual-task-details-toggle"
          onClick={() => setShowDetails(true)}
        >
          + Add category, priority, or estimate
        </button>
      ) : (
        <div className="manual-task-details">
          <input
            className="field-inline"
            placeholder="Category (optional)"
            value={category}
            disabled={createMutation.isPending}
            onChange={(e) => setCategory(e.target.value)}
          />
          <select
            className="field-inline field-priority"
            value={priority}
            disabled={createMutation.isPending}
            onChange={(e) => setPriority(e.target.value as Priority)}
            aria-label="Priority"
          >
            <option value="Low">Low</option>
            <option value="Medium">Medium</option>
            <option value="High">High</option>
          </select>
          <div className="field-estimate-group">
            <input
              className="field-inline field-estimate"
              type="number"
              min={1}
              placeholder="Estimate"
              value={estimate}
              disabled={createMutation.isPending}
              onChange={(e) => setEstimate(e.target.value)}
              aria-label="Estimate in minutes"
            />
            <span className="field-estimate-unit">min</span>
          </div>
        </div>
      )}

      {createMutation.isError && (
        <div className="notice">
          Couldn't add that task just now. Try again when you're ready.
        </div>
      )}
    </form>
  );
}
