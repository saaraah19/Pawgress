/**
 * Mirrors the backend's Pydantic response/request models exactly
 * (productivity/schemas.py, identity/schemas.py).
 */

// --- Domain Model §7 enums, reproduced as literal unions ---
export type Priority = "Low" | "Medium" | "High";
export type TaskStatus = "NotStarted" | "Done";
export type TaskOrigin = "AIGenerated" | "ManuallyCreated";
export type CaptureStatus = "Pending" | "Succeeded" | "Failed";
export type CatMoodState = "Neutral" | "Attentive" | "Content";
// V2 goal hierarchy (Blueprint §13). Ordinal position matches the backend's
// GOAL_TIER_RANK — broader scope first. A Goal's tier is optional; a goal
// with no tier behaves exactly like the original flat MVP goal.
export const GOAL_TIERS = ["Annual", "Quarterly", "Project", "Milestone"] as const;
export type GoalTier = (typeof GOAL_TIERS)[number];

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
  tier: GoalTier | null;
  parentGoalId: string | null;
  createdAt: string;
}

export interface GoalCreateRequest {
  label: string;
  tier?: GoalTier;
}

export interface GoalUpdateRequest {
  label?: string;
  tier?: GoalTier | null;
  parentGoalId?: string | null;
}

export interface CompanionState {
  mood: CatMoodState;
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

export interface Profile {
  user_id: string;
  display_name: string; // FR-1.3 — always present; the neutral default
  // ("Friend") is already applied server-side, so the client never needs
  // to know whether this came from a real name or the placeholder.
  email: string;
}

// --- journal/schemas.py ---
export interface JournalEntry {
  id: string;
  text: string;
  createdAt: string;
  updatedAt: string;
}

export interface JournalEntryCreateRequest {
  text: string;
}

export interface JournalEntryUpdateRequest {
  text: string;
}

// --- habits/schemas.py ---
export type HabitFrequency = "Daily" | "WeeklyCount";

export interface Habit {
  id: string;
  label: string;
  frequency: HabitFrequency;
  weeklyTarget: number | null;
  goalId: string | null;
  // Deliberately a plain accumulating total, not a streak — see
  // habits/models.py's docstring. Never resets, never "breaks."
  totalCompletions: number;
  completedToday: boolean;
  // ISO dates with a completion, scoped to whichever week was requested
  // (see api/client.ts's `weekStart` param) — a display convenience for
  // the week table, not a second lifetime-progress signal.
  completedDates: string[];
  createdAt: string;
}

export interface HabitCreateRequest {
  label: string;
  frequency: HabitFrequency;
  weeklyTarget?: number;
  goalId?: string;
}

export interface HabitUpdateRequest {
  label?: string;
  frequency?: HabitFrequency;
  weeklyTarget?: number | null;
  goalId?: string | null;
}

// --- calendar_integration/schemas.py — read-only Google Calendar (v1) ---
export interface CalendarStatus {
  connected: boolean;
  accountEmail: string | null;
}

export interface CalendarOAuthStart {
  authorizationUrl: string;
}

export interface CalendarEvent {
  id: string;
  title: string;
  start: string;
  end: string;
  allDay: boolean;
  location: string | null;
}