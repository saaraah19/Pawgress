import { useState, type FormEvent } from "react";

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

  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    const trimmed = text.trim();
    if (!trimmed) return;
    onSubmit(trimmed);
  }

  return (
    <form onSubmit={handleSubmit} className="capture-form">
      <textarea
        className="capture-textarea"
        placeholder="What's on your mind?"
        value={text}
        onChange={(e) => setText(e.target.value)}
        rows={4}
        disabled={submitting}
      />
      <button className="primary" type="submit" disabled={submitting || !text.trim()}>
        {submitting ? "Organizing..." : "Capture"}
      </button>
    </form>
  );
}
