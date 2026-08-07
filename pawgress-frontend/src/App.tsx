import { Routes, Route, Navigate } from "react-router-dom";
import { LoginPage } from "./features/auth/LoginPage";
import { RegisterPage } from "./features/auth/RegisterPage";
import { RequireAuth } from "./features/auth/RequireAuth";
import { CapturePage } from "./features/capture/CapturePage";
import { GoalsPage } from "./features/goals/GoalsPage";
import { AccountPage } from "./features/account/AccountPage";
import { AppShell } from "./shared/ui/AppShell";

export function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/register" element={<RegisterPage />} />
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