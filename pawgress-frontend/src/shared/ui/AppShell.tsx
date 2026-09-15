import { type ReactNode } from "react";
import { NavLink } from "react-router-dom";
import { useAuth } from "../../features/auth/AuthContext";

const NAV_ITEMS: { to: string; label: string; end?: boolean }[] = [
  { to: "/", label: "Today", end: true },
  { to: "/planner", label: "Planner" },
  { to: "/goals", label: "Goals" },
  { to: "/journal", label: "Journal" },
  { to: "/habits", label: "Habits" },
  { to: "/calendar", label: "Calendar" },
  { to: "/account", label: "Account" },
];

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
          {NAV_ITEMS.map((item) => (
            <NavLink key={item.to} className="app-nav-link" to={item.to} end={item.end}>
              {item.label}
            </NavLink>
          ))}
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
