import { useAuth } from "../auth/AuthContext";

/**
 * Deliberately minimal. This exists only to confirm, end to end, that
 * register/login persists a token and that a protected screen renders
 * because of it — not to sketch the real Daily View. The First Capture
 * input and task list replace this entirely in the next piece.
 */
export function HomePlaceholder() {
  const { userId, logout } = useAuth();

  return (
    <div className="page">
      <div className="card">
        <h1>You're logged in</h1>
        <p className="muted">User ID: {userId}</p>
        <p className="muted">
          The capture box and task list aren't built yet — this screen just
          confirms the session is real.
        </p>
        <button className="primary" onClick={logout}>
          Log out
        </button>
      </div>
    </div>
  );
}
