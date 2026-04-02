import { useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../hooks/useAuth";
import Card from "../components/Card";

export default function LoginPage() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const { login } = useAuth();
  const navigate = useNavigate();

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setSubmitting(true);

    try {
      await login(email, password);
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
          <h2 className="text-base font-semibold text-text mb-6">Sign in to your account</h2>

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
                autoComplete="current-password"
                minLength={8}
              />
            </div>

            <button
              type="submit"
              className="btn-primary w-full"
              disabled={submitting}
            >
              {submitting ? "Signing in..." : "Sign In"}
            </button>
          </form>
        </Card>

        <p className="text-center text-xs text-dim mt-6">
          Need access?{" "}
          <a href="mailto:hello@getdynamiq.ai" className="text-accent hover:underline font-medium">
            Contact us
          </a>
        </p>
      </div>
    </div>
  );
}
