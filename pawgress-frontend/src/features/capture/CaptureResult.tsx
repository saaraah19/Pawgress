import type { CaptureResult as CaptureResultType, Priority } from "../../shared/types";

interface CaptureResultProps {
  result: CaptureResultType;
  onRetry: (rawText: string) => void;
  retrying: boolean;
}

const PRIORITY_LABEL: Record<Priority, string> = {
  Low: "Low",
  Medium: "Medium",
  High: "High",
};

/**
 * Three outcomes, deliberately not collapsed into one "did it work" state:
 *
 * 1. failureReason set          -> genuine extraction failure (schema_invalid /
 *    provider_error). Raw text preserved and shown, retry offered (FR-2.7).
 * 2. failureReason null, tasks: [] -> a VALID success outcome (a purely
 *    reflective capture, e.g. golden-set NONACTIONABLE-*). Not an error —
 *    no warning styling, no apologetic copy.
 * 3. failureReason null, tasks.length > 0 -> the ordinary case. Shown
 *    plainly, no celebratory copy (FR-2.5), no exclamation points.
 */
export function CaptureResult({ result, onRetry, retrying }: CaptureResultProps) {
  if (result.failureReason) {
    return (
      <div className="capture-result">
        <div className="notice">
          That didn't come back in a structured way. Nothing you wrote was
          lost — it's still here if you want to try again.
        </div>
        <div className="raw-text-preserved">{result.capture.rawText}</div>
        <button
          className="primary"
          onClick={() => onRetry(result.capture.rawText)}
          disabled={retrying}
        >
          {retrying ? "Trying again..." : "Try again"}
        </button>
      </div>
    );
  }

  if (result.tasks.length === 0) {
    return (
      <div className="capture-result">
        <p className="muted">Nothing here needed turning into a task.</p>
      </div>
    );
  }

  return (
    <div className="capture-result">
      <p className="muted capture-source">"{result.capture.rawText}"</p>
      <ul className="task-list">
        {result.tasks.map((task) => (
          <li key={task.id} className="task-row">
            <span className="task-title">{task.title}</span>
            <span className="task-meta">
              <span className="task-category">{task.category}</span>
              <span className="task-priority">{PRIORITY_LABEL[task.priority]}</span>
              {task.estimateMinutes !== null && (
                <span className="task-estimate">{task.estimateMinutes} min</span>
              )}
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}
