import { createContext, useContext, type ReactNode } from "react";

interface CompanionReactionContextValue {
  reactToCapture: () => void;
}

const CompanionReactionContext = createContext<CompanionReactionContextValue | null>(null);

/**
 * AppShell owns the header's CompanionCharacter (and its ref), but the
 * event that should trigger a reaction — a successful capture — happens in
 * CapturePage, a descendant rendered through routing rather than a direct
 * child. This context bridges the two without prop-drilling through
 * App.tsx's route definitions.
 */
export function CompanionReactionProvider({
  reactToCapture,
  children,
}: {
  reactToCapture: () => void;
  children: ReactNode;
}) {
  return (
    <CompanionReactionContext.Provider value={{ reactToCapture }}>{children}</CompanionReactionContext.Provider>
  );
}

/**
 * Safe to call even where no CompanionReactionProvider is mounted (e.g. an
 * isolated component test) — falls back to a no-op rather than throwing,
 * since a missing companion reaction should never be able to break a page.
 */
export function useCompanionReaction(): CompanionReactionContextValue {
  const ctx = useContext(CompanionReactionContext);
  return ctx ?? { reactToCapture: () => {} };
}
