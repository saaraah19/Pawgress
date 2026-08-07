import { useState, type FormEvent, type KeyboardEvent } from "react";

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
 */
export function CaptureForm({ onSubmit, submitting, initialValue = "" }: CaptureFormProps) {
  const [text, setText] = useState(initialValue);

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
      <button className="primary" type="submit" disabled={submitting || !text.trim()}>
        {submitting ? "Organizing..." : "Capture"}
      </button>
    </form>
  );
}

