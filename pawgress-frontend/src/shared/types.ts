/**
 * Mirrors the backend's Pydantic response/request models exactly
 * (productivity/schemas.py, identity/schemas.py). Kept as a single source of
 * truth on the frontend side so every feature imports from here rather than
 * redefining shapes locally — a field rename on the backend should surface
 * as a compile error here, not a silent runtime mismatch.
 */

// --- Domain Model §7 enums, reproduced as literal unions ---
export type Priority = "Low" | "Medium" | "High";
export type TaskStatus = "NotStarted" | "Done";
export type TaskOrigin = "AIGenerated" | "ManuallyCreated";
export type CaptureStatus = "Pending" | "Succeeded" | "Failed";

// --- productivity/schemas.py ---
export interface Task {
  id: string;
  title: string;
  category: string;
  priority: Priority;
  estimateMinutes: number | null;
  status: TaskStatus;
  origin: TaskOrigin;
  createdAt: string;
}

export interface CaptureResponse {
  id: string;
  rawText: string;
  status: CaptureStatus;
  createdAt: string;
}

export type FailureReason = "schema_invalid" | "provider_error" | null;

export interface CaptureResult {
  capture: CaptureResponse;
  tasks: Task[];
  failureReason: FailureReason;
}

export interface TaskUpdateRequest {
  title?: string;
  category?: string;
  priority?: Priority;
  estimateMinutes?: number | null;
  status?: TaskStatus;
}

// --- identity/schemas.py ---
export interface AuthResponse {
  user_id: string;
  access_token: string;
}
