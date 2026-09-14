import { useEffect, useState, type FormEvent } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useAuth } from "../auth/AuthContext";
import { getProfile, updateProfile, deleteAccount, ApiError } from "../../api/client";
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
 *
 * Account-management floor added 2026-09-13: display-name editing and
 * account deletion. NFR-3/BR-10 required deletion to be architecturally
 * *possible* from day one; this is the first UI that actually lets a user
 * exercise that right themselves, rather than it only existing as a
 * backend capability nobody could reach.
 */
export function AccountPage() {
  const { token, logout } = useAuth();
  const queryClient = useQueryClient();

  const [nameInput, setNameInput] = useState("");
  const [nameSaved, setNameSaved] = useState(false);
  const [confirmingDelete, setConfirmingDelete] = useState(false);
  const [deleteConfirmText, setDeleteConfirmText] = useState("");

  const query = useQuery({
    queryKey: PROFILE_QUERY_KEY,
    queryFn: () => getProfile(token!),
    enabled: !!token,
  });

  useEffect(() => {
    if (query.data) setNameInput(query.data.display_name);
  }, [query.data]);

  const updateNameMutation = useMutation({
    mutationFn: (display_name: string | null) => updateProfile({ display_name }, token!),
    onSuccess: (profile) => {
      queryClient.setQueryData(PROFILE_QUERY_KEY, profile);
      setNameSaved(true);
      setTimeout(() => setNameSaved(false), 2000);
    },
  });

  const deleteMutation = useMutation({
    mutationFn: () => deleteAccount(token!),
    onSuccess: () => {
      // No account left to log out of in the usual sense — this just
      // clears the local session, since the account (and the token's
      // validity) no longer exist server-side.
      logout();
    },
  });

  function handleNameSubmit(e: FormEvent) {
    e.preventDefault();
    const trimmed = nameInput.trim();
    if (query.data && trimmed === query.data.display_name) return;
    updateNameMutation.mutate(trimmed === "" ? null : trimmed);
  }

  const deleteConfirmEmail = query.data?.email ?? "";
  const canConfirmDelete = deleteConfirmText === deleteConfirmEmail;

  return (
    <div className="page">
      <div className="card">
        <h1>Account</h1>

        {query.isLoading && <p className="muted">Loading account...</p>}

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
            <form onSubmit={handleNameSubmit} className="field">
              <label htmlFor="display-name-input">Name</label>
              <input
                id="display-name-input"
                className="field-inline"
                value={nameInput}
                disabled={updateNameMutation.isPending}
                onChange={(e) => setNameInput(e.target.value)}
                onBlur={handleNameSubmit}
              />
              {nameSaved && <span className="muted"> Saved.</span>}
              {updateNameMutation.isError && (
                <div className="notice">
                  {updateNameMutation.error instanceof ApiError
                    ? updateNameMutation.error.message
                    : "Couldn't save that just now."}
                </div>
              )}
            </form>
            <div className="field">
              <label>Email</label>
              <p>{query.data.email}</p>
            </div>
          </>
        )}

        <button className="primary" onClick={logout}>
          Log out
        </button>

        <div className="danger-zone">
          <h2>Delete account</h2>
          {!confirmingDelete ? (
            <button type="button" className="link danger-link" onClick={() => setConfirmingDelete(true)}>
              Delete my account
            </button>
          ) : (
            <div className="danger-zone-confirm">
              <p>
                This permanently deletes your account and everything in it — tasks, goals, habits, journal
                entries, and captures. This can't be undone.
              </p>
              <label htmlFor="delete-confirm-input">
                Type your email address ({deleteConfirmEmail}) to confirm.
              </label>
              <input
                id="delete-confirm-input"
                className="field-inline"
                value={deleteConfirmText}
                disabled={deleteMutation.isPending}
                onChange={(e) => setDeleteConfirmText(e.target.value)}
                autoComplete="off"
              />
              <div className="danger-zone-actions">
                <button
                  type="button"
                  className="danger"
                  disabled={!canConfirmDelete || deleteMutation.isPending}
                  onClick={() => deleteMutation.mutate()}
                >
                  {deleteMutation.isPending ? "Deleting..." : "Permanently delete my account"}
                </button>
                <button
                  type="button"
                  className="link"
                  disabled={deleteMutation.isPending}
                  onClick={() => {
                    setConfirmingDelete(false);
                    setDeleteConfirmText("");
                  }}
                >
                  Cancel
                </button>
              </div>
              {deleteMutation.isError && (
                <div className="notice">Couldn't delete your account just now. Nothing was changed — try again.</div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
