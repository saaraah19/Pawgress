import { Routes, Route, Navigate } from "react-router-dom";
import { LoginPage } from "./features/auth/LoginPage";
import { RegisterPage } from "./features/auth/RegisterPage";
import { ForgotPasswordPage } from "./features/auth/ForgotPasswordPage";
import { ResetPasswordPage } from "./features/auth/ResetPasswordPage";
import { RequireAuth } from "./features/auth/RequireAuth";
import { CapturePage } from "./features/capture/CapturePage";
import { PlannerPage } from "./features/planner/PlannerPage";
import { GoalsPage } from "./features/goals/GoalsPage";
import { JournalPage } from "./features/journal/JournalPage";
import { HabitsPage } from "./features/habits/HabitsPage";
import { CalendarPage } from "./features/calendar/CalendarPage";
import { AccountPage } from "./features/account/AccountPage";
import { AppShell } from "./shared/ui/AppShell";

export function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/register" element={<RegisterPage />} />
      <Route path="/forgot-password" element={<ForgotPasswordPage />} />
      <Route path="/reset-password" element={<ResetPasswordPage />} />
      <Route
        path="/"
        element={
          <RequireAuth>
            <AppShell>
              <CapturePage />
            </AppShell>
          </RequireAuth>
        }
      />
      <Route
        path="/planner"
        element={
          <RequireAuth>
            <AppShell>
              <PlannerPage />
            </AppShell>
          </RequireAuth>
        }
      />
      <Route
        path="/goals"
        element={
          <RequireAuth>
            <AppShell>
              <GoalsPage />
            </AppShell>
          </RequireAuth>
        }
      />
      <Route
        path="/journal"
        element={
          <RequireAuth>
            <AppShell>
              <JournalPage />
            </AppShell>
          </RequireAuth>
        }
      />
      <Route
        path="/habits"
        element={
          <RequireAuth>
            <AppShell>
              <HabitsPage />
            </AppShell>
          </RequireAuth>
        }
      />
      <Route
        path="/calendar"
        element={
          <RequireAuth>
            <AppShell>
              <CalendarPage />
            </AppShell>
          </RequireAuth>
        }
      />
      <Route
        path="/account"
        element={
          <RequireAuth>
            <AppShell>
              <AccountPage />
            </AppShell>
          </RequireAuth>
        }
      />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}