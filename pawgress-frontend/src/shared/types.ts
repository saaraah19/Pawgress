/**
 * Mirrors the backend's Pydantic response/request models exactly
 * (productivity/schemas.py, identity/schemas.py).
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
  category: string | null; // nullable — manual tasks may leave this unset (AC-3.4.1)
  priority: Priority;
  estimateMinutes: number | null;
  status: TaskStatus;
  origin: TaskOrigin;
  goalId: string | null;
  createdAt: string;
}

export interface Goal {
  id: string;
  label: string;
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
  goalId?: string | null;
}

export interface ManualTaskCreateRequest {
  title: string;
  category?: string;
  priority?: Priority;
  estimateMinutes?: number;
}

// --- identity/schemas.py ---
export interface AuthResponse {
  user_id: string;
  access_token: string;
}