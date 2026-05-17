import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Sparkles } from "lucide-react";
import Card from "../Card";
import Badge from "../Badge";
import EmptyState from "../EmptyState";
import TriageRunModal from "../approvals/TriageRunModal";
import { api, type MonitoringJob } from "../../lib/api";
import { formatDateTime, formatDuration, formatRelative } from "../../lib/utils";

const POLL_INTERVAL_MS = 5000;

interface RunSummary {
  approved?: number;
  rejected?: number;
  deferred?: number;
  total_decisions?: number;
  batch_size?: number;
}

function extractCounts(job: MonitoringJob): RunSummary {
  return (job.result_summary || {}) as RunSummary;
}

export default function TriageRunsTab() {
  const [runs, setRuns] = useState<MonitoringJob[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [modalOpen, setModalOpen] = useState(false);

  const refresh = useCallback(async () => {
    try {
      const data = await api.triage.listRuns({ limit: "50" });
      setRuns(data);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load triage runs");
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  // Poll while any run is still in flight.
  useEffect(() => {
    if (runs === null) return;
    const inFlight = runs.some((r) => r.status === "running" || r.status === "pending");
    if (!inFlight) return;
    const id = window.setInterval(refresh, POLL_INTERVAL_MS);
    return () => window.clearInterval(id);
  }, [runs, refresh]);

  const onModalClose = () => {
    setModalOpen(false);
    refresh();
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between flex-wrap gap-3">
        <span className="text-sm text-dim">
          {runs ? `${runs.length} recent triage runs` : "Loading…"}
        </span>
        <button
          className="btn-primary flex items-center gap-1.5 text-sm py-1.5 px-3"
          onClick={() => setModalOpen(true)}
        >
          <Sparkles className="w-4 h-4" /> New triage run
        </button>
      </div>

      {error && (
        <Card className="p-4 text-sm text-danger">Error: {error}</Card>
      )}

      <Card className="overflow-hidden">
        {runs === null ? (
          <div className="p-10 text-center text-muted">Loading triage runs…</div>
        ) : runs.length === 0 ? (
          <EmptyState
            icon={Sparkles}
            title="No triage runs yet"
            description="Click 'New triage run' to let the AI review pending approvals against their sources."
            action={{ label: "New triage run", onClick: () => setModalOpen(true) }}
          />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-bg/40 text-left text-xs uppercase tracking-wide text-dim">
                <tr>
                  <th className="px-4 py-2 font-semibold">Run</th>
                  <th className="px-4 py-2 font-semibold">Status</th>
                  <th className="px-4 py-2 font-semibold">Started</th>
                  <th className="px-4 py-2 font-semibold">Duration</th>
                  <th className="px-4 py-2 font-semibold">Model</th>
                  <th className="px-4 py-2 font-semibold">Cost</th>
                  <th className="px-4 py-2 font-semibold">Approved</th>
                  <th className="px-4 py-2 font-semibold">Rejected</th>
                  <th className="px-4 py-2 font-semibold">Deferred</th>
                </tr>
              </thead>
              <tbody>
                {runs.map((r) => {
                  const counts = extractCounts(r);
                  return (
                    <tr key={r.id} className="border-t border-border/60 hover:bg-hover/30">
                      <td className="px-4 py-2 font-mono">
                        <Link
                          to={`/app/agent-monitoring/runs/${r.id}`}
                          className="text-accent hover:underline"
                        >
                          #{r.id}
                        </Link>
                      </td>
                      <td className="px-4 py-2">
                        <Badge value={r.status} />
                      </td>
                      <td className="px-4 py-2 text-xs whitespace-nowrap">
                        <div>{formatDateTime(r.started_at || r.created_at)}</div>
                        <div className="text-dim">
                          {formatRelative(r.started_at || r.created_at)}
                        </div>
                      </td>
                      <td className="px-4 py-2 whitespace-nowrap text-xs text-dim">
                        {formatDuration(r.started_at, r.completed_at)}
                      </td>
                      <td className="px-4 py-2 font-mono text-xs">
                        {r.model || "—"}
                      </td>
                      <td className="px-4 py-2 tabular-nums">
                        {r.estimated_cost_usd !== "0"
                          ? `$${r.estimated_cost_usd}`
                          : <span className="text-dim">—</span>}
                      </td>
                      <td className="px-4 py-2 tabular-nums text-success">
                        {counts.approved ?? 0}
                      </td>
                      <td className="px-4 py-2 tabular-nums text-danger">
                        {counts.rejected ?? 0}
                      </td>
                      <td className="px-4 py-2 tabular-nums text-warning">
                        {counts.deferred ?? 0}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      <TriageRunModal open={modalOpen} onClose={onModalClose} />
    </div>
  );
}
