import { createContext, useCallback, useEffect, useState, type ReactNode } from "react";

interface User {
  id: number;
  email: string;
  role: "admin" | "user";
}

interface AuthState {
  token: string | null;
  user: User | null;
  isAdmin: boolean;
  isAuthenticated: boolean;
}

interface AuthContextValue extends AuthState {
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string) => Promise<void>;
  logout: () => void;
}

const TOKEN_KEY = "taxlens_token";

// eslint-disable-next-line react-refresh/only-export-components
export const AuthContext = createContext<AuthContextValue | null>(null);

export default function AuthProvider({ children }: { children: ReactNode }) {
  const [token, setToken] = useState<string | null>(() => localStorage.getItem(TOKEN_KEY));
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  const clearAuth = useCallback(() => {
    localStorage.removeItem(TOKEN_KEY);
    setToken(null);
    setUser(null);
  }, []);

  // Validate existing token on mount
  useEffect(() => {
    if (!token) {
      setLoading(false);
      return;
    }

    fetch("/v1/auth/me", {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then((res) => {
        if (!res.ok) throw new Error("Invalid token");
        return res.json();
      })
      .then((data: User) => {
        setUser(data);
      })
      .catch(() => {
        clearAuth();
      })
      .finally(() => {
        setLoading(false);
      });
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // Clear auth state when a 401 response removes the token (dispatched from api.ts)
  useEffect(() => {
    const handleLogout = () => {
      setToken(null);
      setUser(null);
    };
    window.addEventListener("auth:logout", handleLogout);
    return () => window.removeEventListener("auth:logout", handleLogout);
  }, []);

  const login = useCallback(async (email: string, password: string) => {
    const res = await fetch("/v1/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password }),
    });

    if (!res.ok) {
      const body = await res.json().catch(() => null);
      throw new Error(body?.detail || `Login failed (${res.status})`);
    }

    const data = await res.json();
    const newToken = data.access_token as string;
    localStorage.setItem(TOKEN_KEY, newToken);
    setToken(newToken);
    setUser(data.user as User);
  }, []);

  const register = useCallback(async (email: string, password: string) => {
    const regRes = await fetch("/v1/auth/register", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password }),
    });

    if (!regRes.ok) {
      const body = await regRes.json().catch(() => null);
      throw new Error(body?.detail || `Registration failed (${regRes.status})`);
    }

    // Auto-login after registration
    const loginRes = await fetch("/v1/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password }),
    });

    if (!loginRes.ok) {
      const body = await loginRes.json().catch(() => null);
      throw new Error(body?.detail || `Auto-login failed (${loginRes.status})`);
    }

    const data = await loginRes.json();
    const newToken = data.access_token as string;
    localStorage.setItem(TOKEN_KEY, newToken);
    setToken(newToken);
    setUser(data.user as User);
  }, []);

  const logout = useCallback(() => {
    clearAuth();
  }, [clearAuth]);

  const isAuthenticated = !!token && !!user;
  const isAdmin = user?.role === "admin";

  // Show nothing while validating existing token
  if (loading) {
    return (
      <div className="h-full flex items-center justify-center bg-bg">
        <div className="flex flex-col items-center gap-3 animate-fadeIn">
          <img src="/logo.svg" alt="TaxLens" className="w-10 h-10" />
          <span className="text-sm text-dim">Loading...</span>
        </div>
      </div>
    );
  }

  return (
    <AuthContext.Provider value={{ token, user, isAdmin, isAuthenticated, login, register, logout }}>
      {children}
    </AuthContext.Provider>
  );
}
