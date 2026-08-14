interface EmptyStateProps {
  message: string;
  /**
   * "resting" — no motion at all (napping). "alert" — a subtle,
   * infrequent look-around motion. Two distinct treatments so the
   * task-list and goals empty states don't read as the same asset
   * reskinned with different words.
   */
  mood?: "resting" | "alert";
}

/**
 * Empty-states-as-companion-moments (Polish Sprint, roadmap item 1).
 *
 * Deliberately NOT used everywhere a list happens to be empty — see
 * docs/PROGRESS.md's Empty States table for which blank moments get this
 * treatment and which are left alone on purpose. The rule: this is for
 * genuine presence moments (nothing here, and that's fine), never for
 * reporting a correctness outcome (e.g. "extraction found nothing" stays
 * Assistant-voiced plain text — Brand §4's test: a line that needs to be
 * trusted as correct is the Assistant's job, not the cat's).
 *
 * Text+glyph only, no illustration — Brand §7's full visual system is
 * still a design-phase deliverable; this is the honest, buildable version
 * of that eventual idea, not a placeholder for it.
 */
export function EmptyState({ message, mood = "resting" }: EmptyStateProps) {
  return (
    <div className="empty-state-companion">
      <span className={`empty-state-glyph empty-state-glyph-${mood}`} aria-hidden="true">
        🐾
      </span>
      <p className="empty-state">{message}</p>
    </div>
  );
}
