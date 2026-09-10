import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useAuth } from "../auth/AuthContext";
import { createCapture, listTasks } from "../../api/client";
import { CaptureForm } from "./CaptureForm";
import { CaptureResult } from "./CaptureResult";
import { TaskList } from "../tasks/TaskList";
import { TASKS_QUERY_KEY } from "../../shared/queryKeys";
import { useCompanionReaction } from "../companion/CompanionReactionContext";
import { COMPANION_EXPRESSION_ASSETS } from "../companion/companionConfig";
import type { CaptureResult as CaptureResultType } from "../../shared/types";

export function CapturePage() {
  const { token } = useAuth();
  const queryClient = useQueryClient();
  const { reactToCapture } = useCompanionReaction();
  const [result, setResult] = useState<CaptureResultType | null>(null);
  const [formKey, setFormKey] = useState(0);

  // Shares the same cache TaskList already populates (TASKS_QUERY_KEY) —
  // this doesn't cause a second network request, just reads the cached
  // result to decide whether to show the "cat waiting beside input"
  // treatment below (companion-character-spec.md §4.3's approved empty
  // state, PROGRESS.md: "passive, ambient, Idle pose, no copy, no reward
  // framing"). Keyed off "the list is currently empty," not off any
  // "is this a brand-new account" flag — deliberately, since the product
  // never distinguishes a first-time empty state from a returned-to-zero
  // one (UX Philosophy §5.5, Return-After-Absence gets zero special
  // treatment); the same calm, non-judgmental presence is appropriate
  // either way.
  const tasksQuery = useQuery({
    queryKey: TASKS_QUERY_KEY,
    queryFn: () => listTasks(token!),
    enabled: !!token,
  });
  const showWaitingCompanion = tasksQuery.data?.length === 0 && !result;

  const mutation = useMutation({
    mutationFn: (rawText: string) => createCapture(rawText, token!),
    onSuccess: async (data) => {
      setResult(data);
      setFormKey((k) => k + 1);
      // Layer D — companion-character-spec.md §5.D: capture is one of the
      // two allowed contextual reaction triggers. Fires regardless of
      // whether tasks were extracted (a zero-task capture is still a
      // genuine, successful moment of being heard).
      reactToCapture();
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

        {showWaitingCompanion && (
          // Deliberately a single static image, not a second live
          // CompanionCharacter instance — the header already renders one
          // independently-animating companion (its own random expression
          // state); mounting a second would risk two visibly different
          // expressions on screen at once, which reads as confusing
          // ("two cats?") rather than as one calm presence. A plain,
          // motionless image is also the more literal reading of
          // "passive" than adding more independent animation.
          <img
            className="capture-waiting-companion"
            src={COMPANION_EXPRESSION_ASSETS.calm}
            alt=""
            aria-hidden="true"
          />
        )}

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