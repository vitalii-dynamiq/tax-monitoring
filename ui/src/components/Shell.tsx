import { NavLink, Outlet, useLocation } from "react-router-dom";
import {
  RiDashboardLine,
  RiMapPinLine,
  RiCalculatorLine,
  RiHistoryLine,
  RiBookOpenLine,
  RiMenuLine,
  RiCloseLine,
  RiLogoutBoxRLine,
  RiKey2Line,
} from "react-icons/ri";
import { cn } from "../lib/utils";
import { useEffect, useState } from "react";
import { api } from "../lib/api";
import { useAuth } from "../hooks/useAuth";
import Badge from "./Badge";

const NAV = [
  { to: "/app", icon: RiDashboardLine, label: "Dashboard" },
  { to: "/app/jurisdictions", icon: RiMapPinLine, label: "Jurisdictions", badgeKey: "pending" as const },
  { to: "/app/calculator", icon: RiCalculatorLine, label: "Calculator" },
  { to: "/app/audit", icon: RiHistoryLine, label: "Audit Log" },
];

const DEV_NAV = [
  { to: "/app/api-keys", icon: RiKey2Line, label: "API Keys" },
  { to: "/app/docs", icon: RiBookOpenLine, label: "API Docs" },
];

export default function Shell() {
  const [dbStatus, setDbStatus] = useState<string>("...");
  const [appVersion, setAppVersion] = useState<string>("");
  const [pendingCount, setPendingCount] = useState(0);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const location = useLocation();
  const { user, isAdmin, logout } = useAuth();

  useEffect(() => {
    api.health()
      .then((h) => {
        setDbStatus(h.database === "connected" ? "Connected" : "Degraded");
        setAppVersion(h.version || "");
      })
      .catch(() => setDbStatus("Offline"));

    api.monitoring.changes({ review_status: "pending" })
      .then((changes) => setPendingCount(changes.length))
      .catch(() => {});
  }, []);

  // Close sidebar on navigation (mobile)
  useEffect(() => {
    setSidebarOpen(false);
  }, [location.pathname]);

  return (
    <div className="flex h-full">
      {/* Mobile header */}
      <div className="fixed top-0 left-0 right-0 h-14 bg-surface border-b border-border flex items-center px-4 gap-3 lg:hidden z-30">
        <button
          onClick={() => setSidebarOpen(!sidebarOpen)}
          className="p-1.5 rounded-md hover:bg-hover transition-colors"
          aria-label="Toggle navigation"
        >
          {sidebarOpen ? <RiCloseLine className="w-5 h-5" /> : <RiMenuLine className="w-5 h-5" />}
        </button>
        <img src="/logo.svg" alt="TaxLens" className="w-7 h-7" />
        <span className="text-sm font-semibold text-text">TaxLens</span>
      </div>

      {/* Overlay for mobile */}
      {sidebarOpen && (
        <div
          className="fixed inset-0 bg-black/30 z-30 lg:hidden animate-fadeIn"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      {/* Sidebar */}
      <aside
        className={cn(
          "w-[260px] flex-shrink-0 border-r border-border bg-surface flex flex-col",
          "fixed inset-y-0 left-0 z-40 transition-transform duration-200 lg:static lg:translate-x-0",
          sidebarOpen ? "translate-x-0" : "-translate-x-full"
        )}
      >
        <div className="h-16 flex items-center px-6 border-b border-border gap-3">
          <img src="/logo.svg" alt="TaxLens" className="w-8 h-8" />
          <span className="text-base font-semibold tracking-tight text-text">
            TaxLens
          </span>
        </div>

        <div className="px-4 pt-5 pb-2">
          <span className="text-xs font-semibold uppercase tracking-widest text-dim px-3">
            Platform
          </span>
        </div>

        <nav className="flex-1 px-4 space-y-0.5 overflow-y-auto">
          {NAV.map(({ to, icon: Icon, label, ...rest }) => (
            <NavLink
              key={to}
              to={to}
              end={to === "/app"}
              className={({ isActive }) =>
                cn(
                  "group relative flex items-center gap-3 px-3 py-2.5 rounded-md text-sm font-medium transition-all duration-150",
                  isActive
                    ? "bg-accent-dim text-accent font-semibold"
                    : "text-muted hover:text-text hover:bg-hover"
                )
              }
            >
              {({ isActive }) => (
                <>
                  {isActive && (
                    <span className="absolute left-0 top-1/2 -translate-y-1/2 w-1 h-5 rounded-full bg-accent" />
                  )}
                  <Icon className="w-5 h-5 flex-shrink-0 opacity-80 group-hover:scale-110 transition-transform duration-150" />
                  <span className="flex-1">{label}</span>
                  {"badgeKey" in rest && rest.badgeKey === "pending" && pendingCount > 0 && isAdmin && (
                    <span className="min-w-[20px] h-5 flex items-center justify-center rounded-full bg-warning text-white text-[11px] font-bold px-1.5">
                      {pendingCount > 99 ? "99+" : pendingCount}
                    </span>
                  )}
                </>
              )}
            </NavLink>
          ))}

          <div className="pt-4 pb-1 px-3">
            <span className="text-xs font-semibold uppercase tracking-widest text-dim">
              Developer
            </span>
          </div>

          {DEV_NAV.map(({ to, icon: Icon, label }) => (
            <NavLink
              key={to}
              to={to}
              className={({ isActive }) =>
                cn(
                  "group relative flex items-center gap-3 px-3 py-2.5 rounded-md text-sm font-medium transition-all duration-150",
                  isActive
                    ? "bg-accent-dim text-accent font-semibold"
                    : "text-muted hover:text-text hover:bg-hover"
                )
              }
            >
              {({ isActive }) => (
                <>
                  {isActive && (
                    <span className="absolute left-0 top-1/2 -translate-y-1/2 w-1 h-5 rounded-full bg-accent" />
                  )}
                  <Icon className="w-5 h-5 flex-shrink-0 opacity-80 group-hover:scale-110 transition-transform duration-150" />
                  {label}
                </>
              )}
            </NavLink>
          ))}
        </nav>

        <div className="px-6 py-4 border-t border-border space-y-3">
          {user && (
            <div className="flex items-center justify-between gap-2">
              <div className="min-w-0 flex-1">
                <div className="text-sm font-medium text-text truncate" title={user.email}>
                  {user.email}
                </div>
                <div className="mt-1">
                  <Badge value={user.role} />
                </div>
              </div>
              <button
                onClick={logout}
                className="p-2 rounded-md text-muted hover:text-danger hover:bg-danger-dim transition-colors flex-shrink-0"
                title="Log out"
                aria-label="Log out"
              >
                <RiLogoutBoxRLine className="w-4.5 h-4.5" />
              </button>
            </div>
          )}
          <div className="flex items-center gap-2.5">
            <div className={cn(
              "w-2 h-2 rounded-full",
              dbStatus === "Connected" ? "bg-success" : dbStatus === "Offline" ? "bg-danger" : "bg-warning"
            )} />
            <span className="text-sm text-dim">Database {dbStatus}</span>
          </div>
          {appVersion && (
            <div className="text-xs text-dim/60">v{appVersion}</div>
          )}
        </div>
      </aside>

      <main className="flex-1 overflow-y-auto bg-bg pt-14 lg:pt-0">
        <Outlet />
      </main>
    </div>
  );
}
