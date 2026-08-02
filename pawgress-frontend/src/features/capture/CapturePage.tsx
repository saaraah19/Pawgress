import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useAuth } from "../auth/AuthContext";
import { createCapture } from "../../api/client";
import { CaptureForm } from "./CaptureForm";
import { CaptureResult } from "./CaptureResult";
import { TaskList, TASKS_QUERY_KEY } from "../tasks/TaskList";
import type { CaptureResult as CaptureResultType } from "../../shared/types";

/**
 * The First Capture signature interaction end to end (UX Philosophy §5.1):
 * raw text in, structured result shown in the same view, no round trip to
 * another screen (FR-2.4), no celebratory framing (FR-2.5).
 */
export function CapturePage() {
  const { token } = useAuth();
  const queryClient = useQueryClient();
  const [result, setResult] = useState<CaptureResultType | null>(null);

  // Bumped on every successful capture so CaptureForm remounts with an empty
  // textarea afterward — a fresh capture, not a hanging draft of the last one.
  const [formKey, setFormKey] = useState(0);

  const mutation = useMutation({
    mutationFn: (rawText: string) => createCapture(rawText, token!),
    onSuccess: (data) => {
      setResult(data);
      setFormKey((k) => k + 1);
      // The flat list below (FR-7.1) should reflect newly extracted tasks
      // immediately, not just the ephemeral capture-result panel above it.
      queryClient.invalidateQueries({ queryKey: TASKS_QUERY_KEY });
    },
  });

  return (
    <div className="page capture-page">
      <div className="capture-card">
        <CaptureForm
          key={formKey}
          onSubmit={(text) => mutation.mutate(text)}
          submitting={mutation.isPending}
        />

        {mutation.isError && !result && (
          <div className="notice">
            Couldn't reach the server just now. Your text wasn't sent — try
            again when you're ready.
          </div>
        )}

        {result && (
          <CaptureResult
            result={result}
            onRetry={(rawText) => mutation.mutate(rawText)}
            retrying={mutation.isPending}
          />
        )}
      </div>

      <div className="task-list-section">
        <TaskList />
      </div>
    </div>
  );
}
