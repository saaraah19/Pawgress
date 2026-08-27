import type {
  AuthResponse,
  CaptureResult,
  Task,
  TaskUpdateRequest,
  Goal,
  GoalCreateRequest,
  GoalUpdateRequest,
  ManualTaskCreateRequest,
  CompanionState,
  Profile,
  JournalEntry,
  JournalEntryCreateRequest,
  JournalEntryUpdateRequest,
  Habit,
  HabitCreateRequest,
  HabitUpdateRequest,
  CalendarStatus,
  CalendarOAuthStart,
  CalendarEvent,
} from "../shared/types";

const API_BASE_URL: string =
  import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
    this.name = "ApiError";
  }
}

async function request<T>(
  path: string,
  options: {
    method?: string;
    body?: unknown;
    token?: string | null;
  } = {}
): Promise<T> {
  const headers: Record<string, string> = {};
  if (options.body !== undefined) {
    headers["Content-Type"] = "application/json";
  }
  if (options.token) {
    headers["Authorization"] = `Bearer ${options.token}`;
  }

  const response = await fetch(`${API_BASE_URL}${path}`, {
    method: options.method ?? "GET",
    headers,
    body: options.body !== undefined ? JSON.stringify(options.body) : undefined,
  });

  if (!response.ok) {
    let detail = `Request failed (${response.status})`;
    try {
      const errorBody = await response.json();
      if (typeof errorBody?.detail === "string") {
        detail = errorBody.detail;
      }
    } catch {
      // Response body wasn't JSON — fall back to the generic message above.
    }
    throw new ApiError(response.status, detail);
  }

  // DELETE /tasks/{id} and DELETE /goals/{id} return 204 No Content —
  // .json() would throw on an empty body, so short-circuit here.
  if (response.status === 204) {
    return undefined as T;
  }

  return (await response.json()) as T;
}

export function register(email: string, password: string): Promise<AuthResponse> {
  return request<AuthResponse>("/auth/register", {
    method: "POST",
    body: { email, password },
  });
}

export function login(email: string, password: string): Promise<AuthResponse> {
  return request<AuthResponse>("/auth/login", {
    method: "POST",
    body: { email, password },
  });
}

export function createCapture(rawText: string, token: string): Promise<CaptureResult> {
  return request<CaptureResult>("/captures", {
    method: "POST",
    body: { rawText },
    token,
  });
}

export function listTasks(token: string): Promise<Task[]> {
  return request<Task[]>("/tasks", { token });
}

export function createTask(payload: ManualTaskCreateRequest, token: string): Promise<Task> {
  return request<Task>("/tasks", { method: "POST", body: payload, token });
}

export function updateTask(
  id: string,
  patch: TaskUpdateRequest,
  token: string
): Promise<Task> {
  return request<Task>(`/tasks/${id}`, {
    method: "PATCH",
    body: patch,
    token,
  });
}

export function deleteTask(id: string, token: string): Promise<void> {
  return request<void>(`/tasks/${id}`, { method: "DELETE", token });
}

export function createGoal(payload: GoalCreateRequest, token: string): Promise<Goal> {
  return request<Goal>("/goals", { method: "POST", body: payload, token });
}

export function listGoals(token: string): Promise<Goal[]> {
  return request<Goal[]>("/goals", { token });
}

export function updateGoal(id: string, patch: GoalUpdateRequest, token: string): Promise<Goal> {
  return request<Goal>(`/goals/${id}`, { method: "PATCH", body: patch, token });
}

export function deleteGoal(id: string, token: string): Promise<void> {
  return request<void>(`/goals/${id}`, { method: "DELETE", token });
}

export function getCompanionState(token: string): Promise<CompanionState> {
  return request<CompanionState>("/companion/state", { token });
}

export function getProfile(token: string): Promise<Profile> {
  return request<Profile>("/auth/me", { token });
}

export function createJournalEntry(payload: JournalEntryCreateRequest, token: string): Promise<JournalEntry> {
  return request<JournalEntry>("/journal", { method: "POST", body: payload, token });
}

export function listJournalEntries(token: string): Promise<JournalEntry[]> {
  return request<JournalEntry[]>("/journal", { token });
}

export function updateJournalEntry(
  id: string,
  patch: JournalEntryUpdateRequest,
  token: string
): Promise<JournalEntry> {
  return request<JournalEntry>(`/journal/${id}`, { method: "PATCH", body: patch, token });
}

export function deleteJournalEntry(id: string, token: string): Promise<void> {
  return request<void>(`/journal/${id}`, { method: "DELETE", token });
}

export function createHabit(payload: HabitCreateRequest, token: string): Promise<Habit> {
  return request<Habit>("/habits", { method: "POST", body: payload, token });
}

export function listHabits(token: string): Promise<Habit[]> {
  return request<Habit[]>("/habits", { token });
}

export function updateHabit(id: string, patch: HabitUpdateRequest, token: string): Promise<Habit> {
  return request<Habit>(`/habits/${id}`, { method: "PATCH", body: patch, token });
}

export function deleteHabit(id: string, token: string): Promise<void> {
  return request<void>(`/habits/${id}`, { method: "DELETE", token });
}

export function markHabitComplete(id: string, token: string): Promise<Habit> {
  return request<Habit>(`/habits/${id}/completions`, { method: "POST", token });
}

/** `date` must be an ISO YYYY-MM-DD string matching the backend's UTC-day
 * convention (see habits/models.py's today_utc()). */
export function unmarkHabitComplete(id: string, date: string, token: string): Promise<Habit> {
  return request<Habit>(`/habits/${id}/completions/${date}`, { method: "DELETE", token });
}

export function getCalendarStatus(token: string): Promise<CalendarStatus> {
  return request<CalendarStatus>("/calendar/status", { token });
}

export function startCalendarOAuth(token: string): Promise<CalendarOAuthStart> {
  return request<CalendarOAuthStart>("/calendar/oauth/start", { token });
}

export function listCalendarEvents(token: string): Promise<CalendarEvent[]> {
  return request<CalendarEvent[]>("/calendar/events", { token });
}

export function disconnectCalendar(token: string): Promise<void> {
  return request<void>("/calendar/connection", { method: "DELETE", token });
}
