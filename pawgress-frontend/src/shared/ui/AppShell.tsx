import type { ReactNode } from "react";
import { Link } from "react-router-dom";
import { useAuth } from "../../features/auth/AuthContext";
import { CompanionIndicator } from "../../features/companion/CompanionIndicator";

export function AppShell({ children }: { children: ReactNode }) {
  const { logout } = useAuth();

  return (
    <div className="app-shell">
      <header className="app-header">
        <div className="app-header-brand">
          <span className="app-header-title">Pawgress</span>
          <CompanionIndicator />
        </div>
        <nav className="app-nav">
          <Link className="link" to="/">
            Today
          </Link>
          <Link className="link" to="/goals">
            Goals
          </Link>
        </nav>
        <button className="link" onClick={logout}>
          Log out
        </button>
      </header>
      <main className="app-main">{children}</main>
    </div>
  );
}