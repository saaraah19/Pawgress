import { useQuery } from "@tanstack/react-query";
import { useAuth } from "../auth/AuthContext";
import { getProfile } from "../../api/client";
import { PROFILE_QUERY_KEY } from "../../shared/queryKeys";

/**
 * FR-1.3 / AC-1.3.1: viewing the profile shows a neutral display-name
 * default rather than requiring the field to proceed — there's nothing
 * to fill in here, no setup step, just what's already true. Utilitarian,
 * Assistant-voiced, no cat presence (UX Philosophy §6 groups "Account and
 * profile settings" explicitly as an ordinary interaction, deliberately
 * outside the five signature ones) — this screen intentionally gets the
 * least design investment in the app, matching Handover §3's framing of
 * auth as infrastructure, not a growth surface.
 */
export function AccountPage() {
  const { token, logout } = useAuth();

  const query = useQuery({
    queryKey: PROFILE_QUERY_KEY,
    queryFn: () => getProfile(token!),
    enabled: !!token,
  });

  return (
    <div className="page">
      <div className="card">
        <h1>Account</h1>

        {query.isLoading && <p className="muted">Loading...</p>}

        {query.isError && (
          <div className="notice">
            Couldn't load your account details just now.{" "}
            <button className="link" onClick={() => query.refetch()}>
              Try again
            </button>
          </div>
        )}

        {query.data && (
          <>
            <div className="field">
              <label>Name</label>
              <p>{query.data.display_name}</p>
            </div>
            <div className="field">
              <label>Email</label>
              <p>{query.data.email}</p>
            </div>
          </>
        )}

        <button className="primary" onClick={logout}>
          Log out
        </button>
      </div>
    </div>
  );
}
