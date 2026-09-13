import { describe, it, expect, vi, afterEach } from "vitest";
import { render, waitFor, screen, cleanup } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { CapturePage } from "./CapturePage";
import { ToastProvider } from "../../shared/ui/ToastProvider";
import type { Task } from "../../shared/types";

/**
 * Covers CapturePage's companion, relocated here from the app-wide header
 * (2026-09-11 positioning slice — see docs/PROGRESS.md). This is now the
 * ONLY CompanionCharacter instance in the whole app, always present near
 * the task list regardless of whether the list is empty — it's no longer
 * a special-cased empty-state-only treatment (the old
 * `.capture-waiting-companion` static image and its `showWaitingCompanion`
 * conditional no longer exist).
 *
 * Mocks the API client and auth context rather than exercising real
 * network calls — this is a UI-conditional-rendering test, not an
 * integration test; the underlying query/mutation behavior already has
 * its own coverage elsewhere (backend tests, useCompanionBehavior.test.ts
 * for the mood/expression logic itself).
 *
 * Queries the companion via its accessible name (role="img" + aria-label,
 * added in the same slice) rather than a CSS class — this doubles as a
 * regression guard for the accessibility fix itself: if the accessible
 * name ever silently disappears, these tests fail along with it.
 */

vi.mock("../auth/AuthContext", () => ({
  useAuth: () => ({ token: "fake-token", userId: "user-1", isAuthenticated: true, logout: vi.fn() }),
}));

const mockListTasks = vi.fn<() => Promise<Task[]>>();
const mockListGoals = vi.fn(async () => []);
const mockGetCompanionState = vi.fn(async () => ({ mood: "Neutral" as const }));

vi.mock("../../api/client", async () => {
  const actual = await vi.importActual<typeof import("../../api/client")>("../../api/client");
  return {
    ...actual,
    listTasks: () => mockListTasks(),
    listGoals: () => mockListGoals(),
    createCapture: vi.fn(),
    getCompanionState: () => mockGetCompanionState(),
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

describe("CapturePage — companion presence near the task list", () => {
  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it("shows the companion (by its accessible name) once mood has loaded, even with an empty task list", async () => {
    mockListTasks.mockResolvedValue([]);
    renderCapturePage();

    await waitFor(() => {
      expect(screen.getByRole("img", { name: /your companion/i })).not.toBeNull();
    });
  });

  it("still shows the companion once at least one task exists — presence is no longer empty-state-only", async () => {
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
    renderCapturePage();

    // Wait for the tasks query to resolve (the task row's title input
    // appearing is proof of that). Task titles render as an editable
    // <input value=...> (TaskRow.tsx), not plain text, so this needs
    // findByDisplayValue, not findByText.
    await screen.findByDisplayValue("Buy milk");
    expect(screen.getByRole("img", { name: /your companion/i })).not.toBeNull();
  });

  it("renders nothing for the companion until its own mood query resolves", () => {
    mockListTasks.mockResolvedValue([]);
    mockGetCompanionState.mockReturnValue(new Promise(() => {})); // never resolves
    renderCapturePage();

    // Silent while loading is the intended behavior (Blueprint §4 — a
    // loading spinner for a peripheral element would give it more visual
    // weight than it's supposed to have), not an accident to work around.
    expect(screen.queryByRole("img", { name: /your companion/i })).toBeNull();
  });
});
