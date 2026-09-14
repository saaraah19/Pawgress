import { useState, type FormEvent, type KeyboardEvent } from "react";
import { useAuth } from "../auth/AuthContext";
import { useVoiceRecording, VOICE_CAPTURE_SUPPORTED } from "./useVoiceRecording";

interface CaptureFormProps {
  onSubmit: (rawText: string) => void;
  submitting: boolean;
  /** Lets the parent pre-fill the box on Retry, so the user doesn't have to retype. */
  initialValue?: string;
}

/**
 * FR-2.1: accepts free-form text of arbitrary length, no formatting/tagging
 * required. Deliberately just a textarea — no rich text, no structure
 * imposed on input, per Core Product Principle "conversation is the primary
 * interface."
 *
 * Voice capture (2026-09-13): a mic button next to the textarea records,
 * transcribes, and drops the result into the SAME textarea a typed capture
 * would use — never auto-submits. See useVoiceRecording.ts for the full
 * reasoning on why transcription errors are handled the same way as typos,
 * not as a separate correction flow.
 */
export function CaptureForm({ onSubmit, submitting, initialValue = "" }: CaptureFormProps) {
  const { token } = useAuth();
  const [text, setText] = useState(initialValue);

  const appendTranscript = (transcribed: string) => {
    setText((current) => (current.trim() ? `${current.trim()} ${transcribed}` : transcribed));
  };

  const { isRecording, isTranscribing, error: voiceError, startRecording, stopRecording } = useVoiceRecording(
    token,
    appendTranscript
  );

  function submit() {
    const trimmed = text.trim();
    if (!trimmed || submitting) return;
    onSubmit(trimmed);
  }

  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    submit();
  }

  // Cmd/Ctrl+Enter to submit — the single highest-leverage shortcut for a
  // product whose core loop is "type, then act" (this interaction happens
  // more than any other in the app). Plain Enter is left alone since a
  // capture is often genuinely multi-line.
  function handleKeyDown(e: KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) {
      e.preventDefault();
      submit();
    }
  }

  const voiceBusy = isRecording || isTranscribing;

  return (
    <form onSubmit={handleSubmit} className="capture-form">
      <textarea
        className="capture-textarea"
        placeholder="What's on your mind?"
        aria-label="Capture your thoughts"
        value={text}
        onChange={(e) => setText(e.target.value)}
        onKeyDown={handleKeyDown}
        rows={4}
        disabled={submitting}
      />
      <div className="capture-form-actions">
        {VOICE_CAPTURE_SUPPORTED && (
          <button
            type="button"
            className={`mic-button${isRecording ? " is-recording" : ""}`}
            disabled={submitting || isTranscribing}
            onClick={isRecording ? stopRecording : startRecording}
            aria-pressed={isRecording}
            aria-label={isRecording ? "Stop recording" : "Record a voice note"}
          >
            {isTranscribing ? "..." : isRecording ? "■" : "🎙"}
          </button>
        )}
        <button className="primary" type="submit" disabled={submitting || voiceBusy || !text.trim()}>
          {submitting ? "Organizing..." : "Capture"}
        </button>
      </div>
      <p className="capture-voice-status" role="status" aria-live="polite">
        {isRecording ? "Recording... tap the square to stop." : isTranscribing ? "Transcribing..." : ""}
      </p>
      {voiceError && <div className="notice">{voiceError}</div>}
    </form>
  );
}

