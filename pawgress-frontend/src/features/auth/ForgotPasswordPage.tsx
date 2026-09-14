import { useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { requestPasswordReset, ApiError } from "../../api/client";

/**
 * Pre-deployment security pass (2026-09-13). Always shows the same
 * success message whether or not the email is registered — same
 * "don't leak account existence" posture as identity/routes.py's login
 * error message (see request_password_reset's docstring on the backend).
 *
 * NOTE: the backend logs the reset link rather than emailing it, until a
 * real email provider is chosen and wired up (identity/password_reset.py) —
 * this page's flow is real and testable end-to-end, but "check your
 * email" isn't literally true yet in this environment.
 */
export function ForgotPasswordPage() {
  const [email, setEmail] = useState("");
  const [submitted, setSubmitted] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      await requestPasswordReset(email);
      setSubmitted(true);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Something went wrong. Try again.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="page">
      <div className="card">
        <h1>Reset your password</h1>
        {submitted ? (
          <p>If that email has an account, a reset link has been sent.</p>
        ) : (
          <>
            {error && <div className="notice">{error}</div>}
            <form onSubmit={handleSubmit}>
              <div className="field">
                <label htmlFor="email">Email</label>
                <input
                  id="email"
                  type="email"
                  autoComplete="email"
                  required
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                />
              </div>
              <button className="primary" type="submit" disabled={submitting}>
                {submitting ? "Sending..." : "Send reset link"}
              </button>
            </form>
          </>
        )}
        <div className="switch-row">
          <Link to="/login">Back to log in</Link>
        </div>
      </div>
    </div>
  );
}
