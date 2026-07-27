import {
  createContext,
  useContext,
  useState,
  useCallback,
  useMemo,
  type ReactNode,
} from "react";
import * as api from "../../api/client";

const STORAGE_KEY = "pawgress_auth";

interface StoredAuth {
  userId: string;
  token: string;
}

interface AuthContextValue {
  userId: string | null;
  token: string | null;
  isAuthenticated: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

function readStoredAuth(): StoredAuth | null {
  const raw = localStorage.getItem(STORAGE_KEY);
  if (!raw) return null;
  try {
    const parsed = JSON.parse(raw);
    if (typeof parsed.userId === "string" && typeof parsed.token === "string") {
      return parsed;
    }
    return null;
  } catch {
    return null;
  }
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [auth, setAuth] = useState<StoredAuth | null>(() => readStoredAuth());

  const persist = useCallback((next: StoredAuth | null) => {
    if (next) {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
    } else {
      localStorage.removeItem(STORAGE_KEY);
    }
    setAuth(next);
  }, []);

  const login = useCallback(
    async (email: string, password: string) => {
      const result = await api.login(email, password);
      persist({ userId: result.user_id, token: result.access_token });
    },
    [persist]
  );

  const register = useCallback(
    async (email: string, password: string) => {
      const result = await api.register(email, password);
      // FR-1.1: account creation authenticates the user immediately, no
      // separate login step required ("...the user is authenticated into
      // the app without additional setup steps").
      persist({ userId: result.user_id, token: result.access_token });
    },
    [persist]
  );

  const logout = useCallback(() => {
    persist(null);
  }, [persist]);

  const value = useMemo<AuthContextValue>(
    () => ({
      userId: auth?.userId ?? null,
      token: auth?.token ?? null,
      isAuthenticated: auth !== null,
      login,
      register,
      logout,
    }),
    [auth, login, register, logout]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return ctx;
}
