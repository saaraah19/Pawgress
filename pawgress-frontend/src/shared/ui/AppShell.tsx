import type { ReactNode } from "react";
import { useAuth } from "../../features/auth/AuthContext";

export function AppShell({ children }: { children: ReactNode }) {
  const { logout } = useAuth();

  return (
    <div className="app-shell">
      <header className="app-header">
        <span className="app-header-title">Pawgress</span>
        <button className="link" onClick={logout}>
          Log out
        </button>
      </header>
      <main className="app-main">{children}</main>
    </div>
  );
}
