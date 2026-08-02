import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useAuth } from "../auth/AuthContext";
import { createCapture } from "../../api/client";
import { CaptureForm } from "./CaptureForm";
import { CaptureResult } from "./CaptureResult";
import { TaskList } from "../tasks/TaskList";
import { TASKS_QUERY_KEY } from "../../shared/queryKeys";
import type { CaptureResult as CaptureResultType } from "../../shared/types";

export function CapturePage() {
  const { token } = useAuth();
  const queryClient = useQueryClient();
  const [result, setResult] = useState<CaptureResultType | null>(null);
  const [formKey, setFormKey] = useState(0);

  const mutation = useMutation({
    mutationFn: (rawText: string) => createCapture(rawText, token!),
    onSuccess: (data) => {
      setResult(data);
      setFormKey((k) => k + 1);
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