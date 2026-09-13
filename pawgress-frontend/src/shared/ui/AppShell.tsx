import { type ReactNode } from "react";
import { Link } from "react-router-dom";
import { useAuth } from "../../features/auth/AuthContext";

export function AppShell({ children }: { children: ReactNode }) {
  const { logout } = useAuth();

  return (
    <div className="app-shell">
      <a className="skip-link" href="#main-content">
        Skip to content
      </a>
      <header className="app-header">
        <div className="app-header-brand">
          <span className="app-header-title">Pawgress</span>
        </div>
        <nav className="app-nav" aria-label="Main">
          <Link className="link" to="/">
            Today
          </Link>
          <Link className="link" to="/goals">
            Goals
          </Link>
          <Link className="link" to="/journal">
            Journal
          </Link>
          <Link className="link" to="/habits">
            Habits
          </Link>
          <Link className="link" to="/calendar">
            Calendar
          </Link>
          <Link className="link" to="/account">
            Account
          </Link>
        </nav>
        <button className="link" onClick={logout}>
          Log out
        </button>
      </header>
      <main id="main-content" className="app-main">
        {children}
      </main>
    </div>
  );
}
