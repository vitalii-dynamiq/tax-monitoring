import { NavLink, Outlet, useLocation } from "react-router-dom";
import {
  RiDashboardLine,
  RiMapPinLine,
  RiCalculatorLine,
  RiBookOpenLine,
  RiMenuLine,
  RiCloseLine,
  RiLogoutBoxRLine,
  RiKey2Line,
  RiSideBarLine,
  RiCheckboxCircleLine,
} from "react-icons/ri";
import { cn } from "../lib/utils";
import { useEffect, useState } from "react";
import { api } from "../lib/api";
import { useAuth } from "../hooks/useAuth";
import Badge from "./Badge";

type NavEntry = {
  to: string;
  icon: typeof RiDashboardLine;
  label: string;
  badgeKey?: "pending" | "approvals";
  adminOnly?: boolean;
};

const NAV: NavEntry[] = [
  { to: "/app", icon: RiDashboardLine, label: "Dashboard" },
  { to: "/app/jurisdictions", icon: RiMapPinLine, label: "Jurisdictions", badgeKey: "pending" },
  { to: "/app/calculator", icon: RiCalculatorLine, label: "Calculator" },
  { to: "/app/approvals", icon: RiCheckboxCircleLine, label: "Approvals", badgeKey: "approvals", adminOnly: true },
];

const DEV_NAV = [
  { to: "/app/api-keys", icon: RiKey2Line, label: "API Keys" },
  { to: "/app/docs", icon: RiBookOpenLine, label: "API Docs" },
];

export default function Shell() {
  const [pendingCount, setPendingCount] = useState(0);
  const [approvalCount, setApprovalCount] = useState(0);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [collapsed, setCollapsed] = useState(() => localStorage.getItem("sidebar_collapsed") === "true");
  const location = useLocation();
  const { user, isAdmin, logout } = useAuth();

  useEffect(() => {
    api.monitoring.changes({ review_status: "pending" })
      .then((changes) => setPendingCount(changes.length))
      .catch(() => {});
  }, []);

  useEffect(() => {
    if (!isAdmin) return;
    api.approvals.summary()
      .then((s) => setApprovalCount(s.total_pending_rates + s.total_pending_rules))
      .catch(() => {});
  }, [isAdmin, location.pathname]);

  // Close sidebar on navigation (mobile)
  useEffect(() => {
    setSidebarOpen(false);
  }, [location.pathname]);

  const toggleCollapsed = () => {
    const next = !collapsed;
    setCollapsed(next);
    localStorage.setItem("sidebar_collapsed", String(next));
  };

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
          "flex-shrink-0 border-r border-border bg-surface flex flex-col transition-all duration-200",
          "fixed inset-y-0 left-0 z-40 lg:static lg:translate-x-0",
          sidebarOpen ? "translate-x-0" : "-translate-x-full",
          collapsed ? "w-[68px]" : "w-[260px]"
        )}
      >
        <div className={cn("h-16 flex items-center border-b border-border gap-3", collapsed ? "justify-center px-2" : "px-6")}>
          <img src="/logo.svg" alt="TaxLens" className="w-8 h-8 flex-shrink-0" />
          {!collapsed && (
            <span className="text-base font-semibold tracking-tight text-text">
              TaxLens
            </span>
          )}
          <button
            onClick={toggleCollapsed}
            className={cn(
              "hidden lg:flex items-center justify-center rounded-md text-muted hover:text-text hover:bg-hover transition-colors w-7 h-7",
              collapsed ? "" : "ml-auto"
            )}
            title={collapsed ? "Expand sidebar" : "Collapse sidebar"}
          >
            <RiSideBarLine className={cn("w-4 h-4 transition-transform", collapsed && "rotate-180")} />
          </button>
        </div>

        {!collapsed && (
          <div className="px-4 pt-5 pb-2">
            <span className="text-xs font-semibold uppercase tracking-widest text-dim px-3">
              Platform
            </span>
          </div>
        )}

        <nav className={cn("flex-1 space-y-0.5 overflow-y-auto", collapsed ? "px-2 pt-4" : "px-4")}>
          {NAV.filter((entry) => !entry.adminOnly || isAdmin).map(({ to, icon: Icon, label, badgeKey }) => {
            const badgeCount =
              badgeKey === "pending" ? pendingCount :
              badgeKey === "approvals" ? approvalCount : 0;
            const showBadge = !collapsed && badgeCount > 0 && isAdmin;
            return (
              <NavLink
                key={to}
                to={to}
                end={to === "/app"}
                title={collapsed ? label : undefined}
                className={({ isActive }) =>
                  cn(
                    "group relative flex items-center rounded-md text-sm font-medium transition-all duration-150",
                    collapsed ? "justify-center px-0 py-2.5" : "gap-3 px-3 py-2.5",
                    isActive
                      ? "bg-accent-dim text-accent font-semibold"
                      : "text-muted hover:text-text hover:bg-hover"
                  )
                }
              >
                {({ isActive }) => (
                  <>
                    {isActive && !collapsed && (
                      <span className="absolute left-0 top-1/2 -translate-y-1/2 w-1 h-5 rounded-full bg-accent" />
                    )}
                    <Icon className="w-5 h-5 flex-shrink-0 opacity-80 group-hover:scale-110 transition-transform duration-150" />
                    {!collapsed && <span className="flex-1">{label}</span>}
                    {showBadge && (
                      <span className="min-w-[20px] h-5 flex items-center justify-center rounded-full bg-warning text-white text-[11px] font-bold px-1.5">
                        {badgeCount > 99 ? "99+" : badgeCount}
                      </span>
                    )}
                  </>
                )}
              </NavLink>
            );
          })}

          {!collapsed && (
            <div className="pt-4 pb-1 px-3">
              <span className="text-xs font-semibold uppercase tracking-widest text-dim">
                Developer
              </span>
            </div>
          )}

          {DEV_NAV.map(({ to, icon: Icon, label }) => (
            <NavLink
              key={to}
              to={to}
              title={collapsed ? label : undefined}
              className={({ isActive }) =>
                cn(
                  "group relative flex items-center rounded-md text-sm font-medium transition-all duration-150",
                  collapsed ? "justify-center px-0 py-2.5" : "gap-3 px-3 py-2.5",
                  isActive
                    ? "bg-accent-dim text-accent font-semibold"
                    : "text-muted hover:text-text hover:bg-hover"
                )
              }
            >
              {({ isActive }) => (
                <>
                  {isActive && !collapsed && (
                    <span className="absolute left-0 top-1/2 -translate-y-1/2 w-1 h-5 rounded-full bg-accent" />
                  )}
                  <Icon className="w-5 h-5 flex-shrink-0 opacity-80 group-hover:scale-110 transition-transform duration-150" />
                  {!collapsed && label}
                </>
              )}
            </NavLink>
          ))}
        </nav>

        <div className={cn("border-t border-border", collapsed ? "px-2 py-3" : "px-6 py-4 space-y-3")}>
          {user && !collapsed && (
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
          {user && collapsed && (
            <button
              onClick={logout}
              className="w-full flex justify-center p-2 rounded-md text-muted hover:text-danger hover:bg-danger-dim transition-colors"
              title="Log out"
              aria-label="Log out"
            >
              <RiLogoutBoxRLine className="w-4.5 h-4.5" />
            </button>
          )}
        </div>
      </aside>

      <main className="flex-1 overflow-y-auto bg-bg pt-14 lg:pt-0">
        <Outlet />
      </main>
    </div>
  );
}
