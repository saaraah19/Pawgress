import { createContext, useCallback, useContext, useRef, useState, type ReactNode } from "react";

/**
 * shared/ui/ToastProvider.tsx
 *
 * A small, dependency-free toast system. Built specifically to replace
 * confirmation dialogs (AC-3.5.1 explicitly rules those out for task
 * deletion) with instant action + a brief, undoable acknowledgment
 * instead — the same tradeoff the whole product is built around
 * (Blueprint §4: "every AI action must be cheap to undo," extended here
 * to a direct user action).
 *
 * Deliberately narrow: one message, an optional single action, a fixed
 * auto-dismiss window. Not a general notification system — Pawgress
 * doesn't have a notification system, and this isn't meant to become
 * one by accretion (System Architecture §1's governing constraint,
 * applied to frontend infrastructure this time, not just backend).
 */

interface ToastOptions {
  message: string;
  actionLabel?: string;
  onAction?: () => void;
  durationMs?: number;
}

interface ToastItem extends ToastOptions {
  id: string;
  leaving: boolean;
}

interface ToastContextValue {
  showToast: (options: ToastOptions) => void;
}

const ToastContext = createContext<ToastContextValue | null>(null);

const DEFAULT_DURATION_MS = 5000;
const LEAVE_ANIMATION_MS = 240; // matches --duration-settle in index.css

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<ToastItem[]>([]);
  const timers = useRef<Map<string, ReturnType<typeof setTimeout>>>(new Map());

  const dismiss = useCallback((id: string) => {
    setToasts((prev) => prev.map((t) => (t.id === id ? { ...t, leaving: true } : t)));
    // Give the CSS leave animation time to play before actually removing
    // the node — a toast that just vanishes reads as a glitch, not calm.
    setTimeout(() => {
      setToasts((prev) => prev.filter((t) => t.id !== id));
    }, LEAVE_ANIMATION_MS);
  }, []);

  const showToast = useCallback(
    ({ message, actionLabel, onAction, durationMs = DEFAULT_DURATION_MS }: ToastOptions) => {
      const id = crypto.randomUUID();
      setToasts((prev) => [...prev, { id, message, actionLabel, onAction, durationMs, leaving: false }]);
      const timer = setTimeout(() => dismiss(id), durationMs);
      timers.current.set(id, timer);
    },
    [dismiss]
  );

  const handleAction = (toast: ToastItem) => {
    const timer = timers.current.get(toast.id);
    if (timer) clearTimeout(timer);
    toast.onAction?.();
    dismiss(toast.id);
  };

  return (
    <ToastContext.Provider value={{ showToast }}>
      {children}
      <div className="toast-region" role="status" aria-live="polite">
        {toasts.map((toast) => (
          <div key={toast.id} className={`toast${toast.leaving ? " is-leaving" : ""}`}>
            <span>{toast.message}</span>
            {toast.actionLabel && (
              <button className="link" onClick={() => handleAction(toast)}>
                {toast.actionLabel}
              </button>
            )}
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}

export function useToast(): ToastContextValue {
  const ctx = useContext(ToastContext);
  if (!ctx) {
    throw new Error("useToast must be used within a ToastProvider");
  }
  return ctx;
}
