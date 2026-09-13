import { useRef, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useAuth } from "../auth/AuthContext";
import { createCapture } from "../../api/client";
import { CaptureForm } from "./CaptureForm";
import { CaptureResult } from "./CaptureResult";
import { TaskList } from "../tasks/TaskList";
import { TASKS_QUERY_KEY } from "../../shared/queryKeys";
import { CompanionCharacter, type CompanionCharacterHandle } from "../companion/CompanionCharacter";
import type { CaptureResult as CaptureResultType } from "../../shared/types";

export function CapturePage() {
  const { token } = useAuth();
  const queryClient = useQueryClient();
  const companionRef = useRef<CompanionCharacterHandle>(null);
  const [result, setResult] = useState<CaptureResultType | null>(null);
  const [formKey, setFormKey] = useState(0);

  const mutation = useMutation({
    mutationFn: (rawText: string) => createCapture(rawText, token!),
    onSuccess: async (data) => {
      setResult(data);
      setFormKey((k) => k + 1);
      // Layer D — companion-character-spec.md §5.D: capture is one of the
      // two allowed contextual reaction triggers. Fires regardless of
      // whether tasks were extracted (a zero-task capture is still a
      // genuine, successful moment of being heard). Called directly on the
      // locally-owned ref now that this page owns the sole companion
      // instance — no more cross-tree context bridge needed for this.
      companionRef.current?.reactToCapture();
      await queryClient.invalidateQueries({ queryKey: TASKS_QUERY_KEY });

      // Quiet Correction (UX Philosophy §5.2) is arguably as important as
      // the capture itself — this moves attention straight to the first
      // newly-created task's editable title in the persistent list below,
      // so a keyboard-first user can start correcting immediately without
      // reaching for the mouse or hunting for it on the page. Scrolls
      // instantly rather than smoothly under prefers-reduced-motion.
      const firstTaskId = data.tasks[0]?.id;
      if (firstTaskId) {
        requestAnimationFrame(() => {
          const el = document.getElementById(`task-title-${firstTaskId}`);
          if (!el) return;
          const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
          el.scrollIntoView({ behavior: reduceMotion ? "auto" : "smooth", block: "center" });
          (el as HTMLInputElement).focus({ preventScroll: true });
        });
      }
    },
  });

  return (
    <div className="page capture-page">
      <div className="capture-card">
        <h1>Today</h1>

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
        {/*
          Relocated here from the app-wide header, per the owner's explicit
          positioning decision — "near the task list, not the header." This
          is now the ONLY CompanionCharacter instance in the whole app
          (AppShell no longer mounts one), so the earlier two-live-instances
          concern that shaped the old empty-state treatment no longer
          applies — there's only ever one companion on screen anywhere,
          full stop. It's always present here, list empty or not, which
          also naturally covers what the old empty-state-only treatment
          was reaching for (a calm presence rather than a blank box) without
          needing a separate conditional image for it.
        */}
        <div className="task-list-companion">
          <CompanionCharacter ref={companionRef} size={40} />
        </div>
        <TaskList />
      </div>
    </div>
  );
}