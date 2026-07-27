import type {
  AuthResponse,
  CaptureResult,
  Task,
  TaskUpdateRequest,
} from "../shared/types";

const API_BASE_URL: string =
  import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

/**
 * Carries the backend's own error message through to the UI rather than
 * replacing it with a generic frontend string. The backend's error copy is
 * deliberately written in the Assistant's plain, non-judgmental voice
 * (identity/routes.py, Brand §6 — "even system errors stay in the
 * Assistant's voice"), so re-wording it here would undo that work.
 */
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
    // FastAPI's default error shape is { "detail": "..." } — matches every
    // handler in identity/routes.py and productivity/routes.py.
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

  // No endpoint in this contract returns an empty body on success.
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
