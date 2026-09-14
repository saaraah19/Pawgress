import { useState, type FormEvent } from "react";
import { useNavigate, useSearchParams, Link } from "react-router-dom";
import { confirmPasswordReset, ApiError } from "../../api/client";

export function ResetPasswordPage() {
  const [searchParams] = useSearchParams();
  const token = searchParams.get("token") ?? "";
  const navigate = useNavigate();

  const [newPassword, setNewPassword] = useState("");
  const [done, setDone] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      await confirmPasswordReset(token, newPassword);
      setDone(true);
      setTimeout(() => navigate("/login", { replace: true }), 2000);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Something went wrong. Try again.");
    } finally {
      setSubmitting(false);
    }
  }

  if (!token) {
    return (
      <div className="page">
        <div className="card">
          <h1>Reset your password</h1>
          <div className="notice">
            This link is missing its reset token. <Link to="/forgot-password">Request a new one.</Link>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="page">
      <div className="card">
        <h1>Set a new password</h1>
        {done ? (
          <p>Your password's been updated. Taking you to log in...</p>
        ) : (
          <>
            {error && <div className="notice">{error}</div>}
            <form onSubmit={handleSubmit}>
              <div className="field">
                <label htmlFor="new-password">New password</label>
                <input
                  id="new-password"
                  type="password"
                  autoComplete="new-password"
                  required
                  minLength={8}
                  value={newPassword}
                  onChange={(e) => setNewPassword(e.target.value)}
                />
              </div>
              <button className="primary" type="submit" disabled={submitting}>
                {submitting ? "Saving..." : "Set new password"}
              </button>
            </form>
          </>
        )}
      </div>
    </div>
  );
}
