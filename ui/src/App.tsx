import { BrowserRouter, Routes, Route, Link, Navigate } from "react-router-dom";
import Shell from "./components/Shell";
import ErrorBoundary from "./components/ErrorBoundary";
import Dashboard from "./pages/Dashboard";
import Jurisdictions from "./pages/Jurisdictions";
import Calculator from "./pages/Calculator";
import AuditLog from "./pages/AuditLog";
import ApiDocs from "./pages/ApiDocs";
import ApiKeysPage from "./pages/ApiKeysPage";
import PendingApprovals from "./pages/PendingApprovals";
import LandingPage from "./pages/LandingPage";
import LoginPage from "./pages/LoginPage";
import { useAuth } from "./hooks/useAuth";

function NotFound() {
  return (
    <div className="p-4 sm:p-10 max-w-[600px] mx-auto text-center">
      <h1 className="text-6xl font-bold text-dim mb-4">404</h1>
      <p className="text-lg text-dim mb-6">Page not found</p>
      <Link to="/app" className="btn-primary inline-block">
        Back to Dashboard
      </Link>
    </div>
  );
}

function RequireAuth({ children }: { children: React.ReactNode }) {
  const { isAuthenticated } = useAuth();
  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }
  return <>{children}</>;
}

export default function App() {
  return (
    <BrowserRouter>
      <ErrorBoundary>
        <Routes>
          <Route index element={<LandingPage />} />
          <Route path="/login" element={<LoginPage />} />
          <Route path="/app" element={<RequireAuth><Shell /></RequireAuth>}>
            <Route index element={<Dashboard />} />
            <Route path="jurisdictions" element={<Jurisdictions />} />
            <Route path="calculator" element={<Calculator />} />
            <Route path="approvals" element={<PendingApprovals />} />
            <Route path="audit" element={<AuditLog />} />
            <Route path="api-keys" element={<ApiKeysPage />} />
            <Route path="docs" element={<ApiDocs />} />
            <Route path="*" element={<NotFound />} />
          </Route>
        </Routes>
      </ErrorBoundary>
    </BrowserRouter>
  );
}
