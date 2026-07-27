import { Navigate } from "react-router-dom";
import type { ReactNode } from "react";
import { useAuth } from "./AuthContext";

/**
 * FR-1.2: a returning, still-valid session should land directly in the app,
 * no login prompt. An unauthenticated visitor is redirected to /login rather
 * than shown a broken authenticated view.
 */
export function RequireAuth({ children }: { children: ReactNode }) {
  const { isAuthenticated } = useAuth();
  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }
  return <>{children}</>;
}
