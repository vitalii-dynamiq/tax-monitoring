import { useMemo, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { Activity, PlayCircle, PauseCircle, AlertTriangle } from "lucide-react";
import PageHeader from "../components/PageHeader";
import PageContainer from "../components/PageContainer";
import Card from "../components/Card";
import StatCard from "../components/StatCard";
import EmptyState from "../components/EmptyState";
import { useApi } from "../hooks/useApi";
import { useAuth } from "../hooks/useAuth";
import { useToast } from "../hooks/useToast";
import {
  api,
  type BulkScheduleUpdate,
  type MonitoringSchedule,
} from "../lib/api";
import ScheduleRow from "../components/agent-schedules/ScheduleRow";
import BulkActionBar from "../components/agent-schedules/BulkActionBar";
import TriageRunsTab from "../components/agent-schedules/TriageRunsTab";

type Tab = "monitoring" | "discovery" | "triage";
type Filter = "all" | "enabled" | "disabled" | "failed24h";

const FILTERS: { id: Filter; label: string }[] = [
  { id: "all", label: "All" },
  { id: "enabled", label: "Enabled" },
  { id: "disabled", label: "Disabled" },
  { id: "failed24h", label: "Failed in last 24h" },
];

export default function AgentSchedules() {
  const { isAdmin } = useAuth();
  const { toast } = useToast();
  const navigate = useNavigate();
  const [params, setParams] = useSearchParams();
  const tab: Tab = (params.get("tab") as Tab) || "monitoring";
  const filter: Filter = (params.get("filter") as Filter) || "all";

  const setFilter = (next: Filter) => {
    const nextParams = new URLSearchParams(params);
    if (next === "all") nextParams.delete("filter");
    else nextParams.set("filter", next);
    setParams(nextParams);
  };

  const [search, setSearch] = useState("");
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [bulkBusy, setBulkBusy] = useState(false);

  // Schedules are only relevant for monitoring/discovery; triage tab fetches
  // its own data inside <TriageRunsTab>. Fetch with a harmless default to
  // keep the useApi-hook count stable across tabs.
  const scheduleJobType = tab === "triage" ? "monitoring" : tab;
  const { data, loading, error, refetch } = useApi(
    () =>
      api.monitoring.listSchedules({ job_type: scheduleJobType, limit: "2000" }),
    [scheduleJobType]
  );

  // Local mirror so per-row edits can update without a refetch flicker
  const [overrides, setOverrides] = useState<Record<number, MonitoringSchedule>>({});

  const schedules = useMemo<MonitoringSchedule[]>(() => {
    const base = data || [];
    return base.map((s) => overrides[s.id] || s);
  }, [data, overrides]);

  const filtered = useMemo(() => {
    let out = schedules;
    if (filter === "enabled") out = out.filter((s) => s.enabled);
    else if (filter === "disabled") out = out.filter((s) => !s.enabled);
    else if (filter === "failed24h") out = out.filter((s) => s.failed_in_last_24h);
    if (search) {
      const q = search.toLowerCase();
      out = out.filter((s) =>
        (s.jurisdiction_code || "").toLowerCase().includes(q),
      );
    }
    return out;
  }, [schedules, search, filter]);

  const stats = useMemo(() => {
    const total = schedules.length;
    const enabled = schedules.filter((s) => s.enabled).length;
    const failing24h = schedules.filter((s) => s.failed_in_last_24h).length;
    return { total, enabled, failing24h };
  }, [schedules]);

  const selectedCodes = useMemo(() => Array.from(selected), [selected]);

  if (!isAdmin) {
    return (
      <PageContainer maxWidth="max-w-4xl">
        <Card className="p-8 text-center">
          <h2 className="text-lg font-semibold text-text mb-2">Admin access required</h2>
          <p className="text-muted mb-4">This page is only available to administrators.</p>
          <button className="btn-primary" onClick={() => navigate("/app")}>
            Back to Dashboard
          </button>
        </Card>
      </PageContainer>
    );
  }

  const switchTab = (next: Tab) => {
    setParams({ tab: next });
    setSelected(new Set());
    setOverrides({});
  };

  const toggleRow = (code: string) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(code)) next.delete(code);
      else next.add(code);
      return next;
    });
  };

  const toggleAll = () => {
    if (selected.size === filtered.length) {
      setSelected(new Set());
    } else {
      setSelected(new Set(filtered.map((s) => s.jurisdiction_code || "").filter(Boolean)));
    }
  };

  const runBulk = async (body: BulkScheduleUpdate) => {
    setBulkBusy(true);
    try {
      const res = await api.monitoring.bulkUpdateSchedules(body);
      const ovr = { ...overrides };
      for (const s of res.updated) ovr[s.id] = s;
      setOverrides(ovr);
      if (res.errors.length > 0) {
        toast(
          `${res.updated.length} updated, ${res.errors.length} failed: ${res.errors
            .slice(0, 3)
            .map((e) => e.code)
            .join(", ")}`,
          "error"
        );
      } else {
        toast(`Updated ${res.updated.length} schedule${res.updated.length === 1 ? "" : "s"}`, "success");
      }
      setSelected(new Set());
      // Refetch in background so server-computed fields (next_run_at, last_run_status) stay fresh.
      refetch();
    } catch (e) {
      toast(e instanceof Error ? e.message : "Bulk update failed", "error");
    } finally {
      setBulkBusy(false);
    }
  };

  const onRowUpdated = (updated: MonitoringSchedule) => {
    setOverrides((prev) => ({ ...prev, [updated.id]: updated }));
  };

  const onRunNow = async (s: MonitoringSchedule) => {
    const code = s.jurisdiction_code;
    if (!code) return;
    try {
      if (s.job_type === "discovery") {
        await api.discovery.triggerRun(code);
      } else {
        await api.monitoring.triggerRun(code);
      }
      toast(`Dispatched ${s.job_type} run for ${code}`, "success");
      // Refetch shortly so last_run_status moves to "running"
      setTimeout(refetch, 1500);
    } catch (e) {
      toast(e instanceof Error ? e.message : "Failed to dispatch", "error");
    }
  };

  return (
    <PageContainer>
      <PageHeader
        title="Agent Monitoring"
        description="Schedule and debug AI agents that monitor taxes and discover sub-jurisdictions."
      />

      {tab !== "triage" && (
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-6">
          <StatCard
            label="Total schedules"
            value={stats.total}
            icon={Activity}
            onClick={() => setFilter("all")}
          />
          <StatCard
            label="Enabled"
            value={stats.enabled}
            accent="success"
            icon={PlayCircle}
            onClick={() => setFilter("enabled")}
          />
          <StatCard
            label="Failed in last 24h"
            value={stats.failing24h}
            sub={stats.failing24h > 0 ? "needs attention — click to filter" : "all healthy"}
            accent={stats.failing24h > 0 ? "danger" : "default"}
            icon={stats.failing24h > 0 ? AlertTriangle : PauseCircle}
            onClick={() => setFilter("failed24h")}
          />
        </div>
      )}

      <div className="flex items-center gap-1 border-b border-border mb-4">
        {(["monitoring", "discovery", "triage"] as Tab[]).map((t) => (
          <button
            key={t}
            onClick={() => switchTab(t)}
            className={`px-4 py-2 text-sm font-medium border-b-2 -mb-px transition-colors ${
              tab === t
                ? "border-accent text-accent"
                : "border-transparent text-muted hover:text-text"
            }`}
          >
            {t === "monitoring"
              ? "Tax Monitoring"
              : t === "discovery"
                ? "Sub-Jurisdiction Discovery"
                : "Triage Runs"}
          </button>
        ))}
      </div>

      {tab === "triage" ? (
        <TriageRunsTab />
      ) : (
      <>
      <div className="flex flex-wrap items-center gap-3 mb-4">
        <input
          type="text"
          placeholder="Search by code…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="text-sm bg-surface border border-border rounded-md px-3 py-2 w-64"
        />
        <div className="flex items-center bg-surface border border-border rounded-md overflow-hidden text-sm">
          {FILTERS.map((f, i) => (
            <button
              key={f.id}
              onClick={() => setFilter(f.id)}
              className={
                "px-3 py-1.5 transition-colors " +
                (i > 0 ? "border-l border-border " : "") +
                (filter === f.id
                  ? "bg-accent-dim text-accent"
                  : "text-muted hover:text-text")
              }
            >
              {f.label}
            </button>
          ))}
        </div>
        <span className="ml-auto text-sm text-dim">
          {filtered.length} of {schedules.length}
        </span>
      </div>

      {selected.size > 0 && (
        <BulkActionBar
          selectedCount={selected.size}
          busy={bulkBusy}
          onClear={() => setSelected(new Set())}
          onEnable={() =>
            runBulk({
              jurisdiction_codes: selectedCodes,
              job_type: tab,
              action: "enable",
            })
          }
          onDisable={() =>
            runBulk({
              jurisdiction_codes: selectedCodes,
              job_type: tab,
              action: "disable",
            })
          }
          onSetCadence={(cadence, cron) =>
            runBulk({
              jurisdiction_codes: selectedCodes,
              job_type: tab,
              action: "set_cadence",
              cadence,
              cron_expression: cron,
            })
          }
        />
      )}

      <Card className="overflow-hidden">
        {loading && (
          <div className="p-10 text-center text-muted">Loading schedules…</div>
        )}
        {error && (
          <div className="p-10 text-center text-danger">Error: {error}</div>
        )}
        {!loading && !error && filtered.length === 0 && (
          <EmptyState
            icon={Activity}
            title="No schedules"
            description={
              tab === "discovery"
                ? "No countries are registered yet. Add a country to schedule discovery."
                : "No jurisdictions are registered yet."
            }
          />
        )}
        {!loading && !error && filtered.length > 0 && (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-bg/40 text-left text-xs uppercase tracking-wide text-dim">
                <tr>
                  <th className="px-3 py-2 w-10">
                    <input
                      type="checkbox"
                      checked={
                        filtered.length > 0 &&
                        selected.size === filtered.length
                      }
                      onChange={toggleAll}
                      className="rounded border-border cursor-pointer"
                      aria-label="Select all"
                    />
                  </th>
                  <th className="px-3 py-2 w-10"></th>
                  <th className="px-3 py-2 font-semibold">Code</th>
                  <th className="px-3 py-2 font-semibold">Enabled</th>
                  <th className="px-3 py-2 font-semibold">Cadence</th>
                  <th className="px-3 py-2 font-semibold">Last run</th>
                  <th className="px-3 py-2 font-semibold">Next run</th>
                  <th className="px-3 py-2 font-semibold"></th>
                </tr>
              </thead>
              <tbody>
                {filtered.map((s) => (
                  <ScheduleRow
                    key={s.id}
                    schedule={s}
                    selected={selected.has(s.jurisdiction_code || "")}
                    onToggleSelect={() => toggleRow(s.jurisdiction_code || "")}
                    onUpdated={onRowUpdated}
                    onRunNow={() => onRunNow(s)}
                    onError={(msg) => toast(msg, "error")}
                  />
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
      </>
      )}
    </PageContainer>
  );
}
