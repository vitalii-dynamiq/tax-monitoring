import { useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../hooks/useAuth";
import Card from "../components/Card";

type Tab = "login" | "register";

export default function LoginPage() {
  const [tab, setTab] = useState<Tab>("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const { login, register } = useAuth();
  const navigate = useNavigate();

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setSubmitting(true);

    try {
      if (tab === "login") {
        await login(email, password);
      } else {
        await register(email, password);
      }
      navigate("/app", { replace: true });
    } catch (err) {
      setError(err instanceof Error ? err.message : "An unexpected error occurred");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="min-h-full flex items-center justify-center bg-bg px-4 py-12 animate-fadeIn">
      <div className="w-full max-w-[420px]">
        {/* Logo */}
        <div className="flex flex-col items-center mb-8">
          <img src="/logo.svg" alt="TaxLens" className="w-12 h-12 mb-3" />
          <h1 className="text-xl font-semibold tracking-tight text-text">TaxLens</h1>
          <p className="text-sm text-dim mt-1">Tax monitoring platform</p>
        </div>

        <Card className="p-6 animate-slideUp">
          {/* Tabs */}
          <div className="flex rounded-md border border-border overflow-hidden mb-6">
            <button
              type="button"
              onClick={() => { setTab("login"); setError(null); }}
              className={
                tab === "login"
                  ? "flex-1 py-2.5 text-sm font-semibold bg-accent text-white transition-colors"
                  : "flex-1 py-2.5 text-sm font-medium text-muted bg-surface hover:bg-hover transition-colors"
              }
            >
              Log In
            </button>
            <button
              type="button"
              onClick={() => { setTab("register"); setError(null); }}
              className={
                tab === "register"
                  ? "flex-1 py-2.5 text-sm font-semibold bg-accent text-white transition-colors"
                  : "flex-1 py-2.5 text-sm font-medium text-muted bg-surface hover:bg-hover transition-colors"
              }
            >
              Register
            </button>
          </div>

          {/* Error */}
          {error && (
            <div className="mb-4 px-3 py-2.5 rounded-md bg-danger-dim border border-danger/25 text-danger text-sm animate-fadeIn">
              {error}
            </div>
          )}

          {/* Form */}
          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label htmlFor="email" className="field-label">
                Email
              </label>
              <input
                id="email"
                type="email"
                className="input-field"
                placeholder="you@company.com"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                autoComplete="email"
                autoFocus
              />
            </div>

            <div>
              <label htmlFor="password" className="field-label">
                Password
              </label>
              <input
                id="password"
                type="password"
                className="input-field"
                placeholder="Enter your password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                autoComplete={tab === "login" ? "current-password" : "new-password"}
                minLength={8}
              />
            </div>

            <button
              type="submit"
              className="btn-primary w-full"
              disabled={submitting}
            >
              {submitting
                ? (tab === "login" ? "Logging in..." : "Creating account...")
                : (tab === "login" ? "Log In" : "Create Account")}
            </button>
          </form>
        </Card>

        <p className="text-center text-xs text-dim mt-6">
          {tab === "login"
            ? "Don't have an account? "
            : "Already have an account? "}
          <button
            type="button"
            onClick={() => { setTab(tab === "login" ? "register" : "login"); setError(null); }}
            className="text-accent hover:underline font-medium"
          >
            {tab === "login" ? "Register" : "Log in"}
          </button>
        </p>
      </div>
    </div>
  );
}
