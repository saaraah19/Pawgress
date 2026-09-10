import { describe, it, expect, vi, afterEach } from "vitest";
import { render, waitFor, screen, cleanup } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { CapturePage } from "./CapturePage";
import { ToastProvider } from "../../shared/ui/ToastProvider";
import type { Task } from "../../shared/types";

/**
 * Covers the First Capture empty-state companion treatment added
 * 2026-08-26 (companion-character-spec.md §4.3, approved 2026-08-09).
 * Mocks the API client and auth context rather than exercising real
 * network calls — this is a UI-conditional-rendering test, not an
 * integration test; the underlying query/mutation behavior already has
 * its own coverage elsewhere (backend tests, and the existing manual
 * verification history for capture/task flows).
 *
 * Queries the companion image via a plain CSS class selector, not
 * getByRole("img") — the image deliberately uses alt="" (correct for a
 * purely decorative element per WAI-ARIA), which means the browser
 * assigns it role="presentation", not role="img". getByRole("img") can
 * never match it regardless of the `hidden` option; a CSS selector is
 * the accurate way to assert on an intentionally non-semantic image.
 */

vi.mock("../auth/AuthContext", () => ({
  useAuth: () => ({ token: "fake-token", userId: "user-1", isAuthenticated: true, logout: vi.fn() }),
}));

vi.mock("../companion/CompanionReactionContext", () => ({
  useCompanionReaction: () => ({ reactToCapture: vi.fn() }),
}));

const mockListTasks = vi.fn<() => Promise<Task[]>>();
const mockListGoals = vi.fn(async () => []);

vi.mock("../../api/client", async () => {
  const actual = await vi.importActual<typeof import("../../api/client")>("../../api/client");
  return {
    ...actual,
    listTasks: () => mockListTasks(),
    listGoals: () => mockListGoals(),
    createCapture: vi.fn(),
  };
});

function renderCapturePage() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <CapturePage />
      </ToastProvider>
    </QueryClientProvider>
  );
}

function findWaitingCompanion(container: HTMLElement): HTMLImageElement | null {
  return container.querySelector(".capture-waiting-companion");
}

describe("CapturePage — First Capture empty-state companion", () => {
  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it("shows the waiting companion image when the task list is empty", async () => {
    mockListTasks.mockResolvedValue([]);
    const { container } = renderCapturePage();

    await waitFor(() => {
      expect(findWaitingCompanion(container)).not.toBeNull();
    });
  });

  it("does not show the waiting companion once at least one task exists", async () => {
    mockListTasks.mockResolvedValue([
      {
        id: "task-1",
        title: "Buy milk",
        category: null,
        priority: "Medium",
        estimateMinutes: null,
        status: "NotStarted",
        origin: "ManuallyCreated",
        goalId: null,
        createdAt: "2026-01-01T00:00:00Z",
      },
    ]);
    const { container } = renderCapturePage();

    // Wait for the tasks query to resolve (the task row's title input
    // appearing is proof of that) before asserting the companion image
    // is absent. Task titles render as an editable <input value=...>
    // (TaskRow.tsx), not plain text, so this needs findByDisplayValue,
    // not findByText.
    await screen.findByDisplayValue("Buy milk");
    expect(findWaitingCompanion(container)).toBeNull();
  });

  it("does not show the waiting companion while the tasks query is still loading", () => {
    mockListTasks.mockReturnValue(new Promise(() => {})); // never resolves
    const { container } = renderCapturePage();

    // Undefined query data (still loading) must not be mistaken for an
    // empty list — the condition explicitly checks tasksQuery.data, not
    // just "no tasks visible yet."
    expect(findWaitingCompanion(container)).toBeNull();
  });
});
