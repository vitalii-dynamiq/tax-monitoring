import { useState } from "react";
import Card from "../../components/Card";
import Badge from "../../components/Badge";
import StatCard from "../../components/StatCard";
import DataTable, { type Column } from "../../components/DataTable";
import ConfirmDialog from "../../components/ConfirmDialog";
import { api, type MonitoringJob } from "../../lib/api";
import { useApi } from "../../hooks/useApi";
import { usePollingApi } from "../../hooks/usePollingApi";
import { useToast } from "../../hooks/useToast";
import { formatDateTime, formatDuration } from "../../lib/utils";
import { Search, CheckCircle2, XCircle, Loader2 } from "lucide-react";

interface PendingJurisdiction {
  code: string;
  name: string;
  local_name: string | null;
  jurisdiction_type: string;
  status: string;
  metadata: Record<string, unknown> | null;
  created_at: string;
}

export default function DiscoveryTab({
  jurisdictionCode,
  countryName,
}: {
  jurisdictionCode: string;
  countryName: string;
}) {
  const { toast } = useToast();
  const [activeJobId, setActiveJobId] = useState<number | null>(null);
  const [showConfirm, setShowConfirm] = useState(false);
  const [triggering, setTriggering] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Fetch discovery jobs for this country
  const {
    data: jobs,
    loading: jobsLoading,
    refetch: refetchJobs,
  } = useApi(
    () => api.discovery.listJobs({ country_code: jurisdictionCode, limit: "50" }),
    [jurisdictionCode]
  );

  // Fetch pending jurisdictions (discovered but not yet approved)
  const {
    data: pendingJurisdictions,
    loading: pendingLoading,
    refetch: refetchPending,
  } = useApi(
    () => api.jurisdictions.list({ country_code: jurisdictionCode.substring(0, 2), status: "pending", limit: "200" }),
    [jurisdictionCode]
  );

  // Poll active job
  const { data: activeJob } = usePollingApi<MonitoringJob>(
    () => api.monitoring.getJob(activeJobId!),
    [activeJobId],
    {
      intervalMs: 3000,
      enabled: activeJobId != null && activeJobId > 0,
      stopWhen: (j) => {
        if (j.status === "completed" || j.status === "failed") {
          refetchJobs();
          refetchPending();
          return true;
        }
        return false;
      },
    }
  );

  const handleRun = async () => {
    setShowConfirm(false);
    setTriggering(true);
    setError(null);
    try {
      const job = await api.discovery.triggerRun(jurisdictionCode);
      toast("Discovery job started", "info");
      setActiveJobId(job.id);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to start discovery");
      toast("Failed to start discovery", "error");
    } finally {
      setTriggering(false);
    }
  };

  const allJobs = jobs || [];
  const pending = pendingJurisdictions || [];
  const completedJobs = allJobs.filter((j) => j.status === "completed");
  const totalDiscovered = completedJobs.reduce(
    (sum, j) => sum + (j.changes_detected || 0),
    0
  );
  const isRunning = activeJob?.status === "pending" || activeJob?.status === "running";
  const isCompleted = activeJob?.status === "completed";
  const isFailed = activeJob?.status === "failed";

  const pendingColumns: Column<PendingJurisdiction>[] = [
    {
      key: "code",
      header: "Code",
      render: (r) => <span className="font-mono text-accent">{r.code}</span>,
    },
    {
      key: "name",
      header: "Name",
      render: (r) => (
        <div>
          <div className="text-text">{r.name}</div>
          {r.local_name && <div className="text-xs text-dim">{r.local_name}</div>}
        </div>
      ),
    },
    {
      key: "type",
      header: "Type",
      render: (r) => <Badge value={r.jurisdiction_type} />,
    },
    {
      key: "status",
      header: "Status",
      render: (r) => <Badge value={r.status} />,
    },
    {
      key: "tax_summary",
      header: "Tax Summary",
      render: (r) => (
        <span className="text-sm text-muted">
          {(r.metadata as Record<string, string>)?.tax_summary || "—"}
        </span>
      ),
    },
    {
      key: "confidence",
      header: "Confidence",
      render: (r) => {
        const conf = (r.metadata as Record<string, number>)?.discovery_confidence;
        return conf != null ? (
          <span className="font-mono text-sm">{(conf * 100).toFixed(0)}%</span>
        ) : (
          <span className="text-dim">—</span>
        );
      },
    },
  ];

  const jobColumns: Column<MonitoringJob>[] = [
    {
      key: "id",
      header: "ID",
      render: (j) => <span className="font-mono text-dim">#{j.id}</span>,
      className: "w-16",
    },
    {
      key: "status",
      header: "Status",
      render: (j) => <Badge value={j.status} />,
    },
    {
      key: "started",
      header: "Started",
      render: (j) => <span className="text-dim text-sm">{formatDateTime(j.started_at)}</span>,
    },
    {
      key: "duration",
      header: "Duration",
      render: (j) => (
        <span className="text-dim text-sm font-mono">
          {j.started_at ? formatDuration(j.started_at, j.completed_at) : "—"}
        </span>
      ),
    },
    {
      key: "found",
      header: "Found",
      render: (j) => (
        <span className={`font-mono ${j.changes_detected > 0 ? "text-accent" : "text-dim"}`}>
          {j.changes_detected}
        </span>
      ),
    },
  ];

  return (
    <div className="space-y-5">
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-5">
        <StatCard
          label="Discovery Runs"
          value={allJobs.length}
          sub="Total runs for this country"
        />
        <StatCard
          label="Jurisdictions Discovered"
          value={totalDiscovered}
          accent={totalDiscovered > 0 ? "success" : "default"}
          sub="Across all runs"
        />
        <StatCard
          label="Pending Review"
          value={pending.length}
          accent={pending.length > 0 ? "warning" : "default"}
          sub="Awaiting approval"
        />
      </div>

      {/* Run discovery */}
      <Card className="p-6">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-sm font-semibold uppercase tracking-widest text-dim">
            Jurisdiction Discovery
          </h3>
        </div>

        {!isRunning && !isCompleted && !isFailed && (
          <div className="flex items-center gap-4">
            <button
              onClick={() => setShowConfirm(true)}
              disabled={triggering}
              className="btn-primary px-5 py-2.5 text-sm flex items-center gap-2"
            >
              <Search className="w-4 h-4" />
              {triggering ? "Starting..." : "Discover Sub-Jurisdictions"}
            </button>
            <span className="text-sm text-dim">
              AI will search for all sub-jurisdictions with accommodation taxes in {countryName}
            </span>
          </div>
        )}

        {isRunning && (
          <div className="flex items-center gap-4 py-2">
            <Loader2 className="w-6 h-6 text-accent animate-spin" />
            <div>
              <div className="text-sm font-medium text-text">Discovering sub-jurisdictions...</div>
              <div className="text-xs text-dim mt-0.5">
                Searching official sources for {countryName}'s accommodation tax structure
              </div>
            </div>
          </div>
        )}

        {isCompleted && activeJob && (
          <div className="flex items-start gap-4 py-2">
            <CheckCircle2 className="w-6 h-6 text-success flex-shrink-0 mt-0.5" />
            <div>
              <div className="text-sm font-medium text-text">Discovery complete</div>
              <div className="text-xs text-dim mt-1 space-y-0.5">
                <div>Jurisdictions found: <span className="font-medium text-text">{activeJob.changes_detected}</span></div>
                {activeJob.result_summary && (
                  <div>
                    Sources checked: {(activeJob.result_summary as Record<string, number>).sources_checked ?? "—"}
                  </div>
                )}
                <div>Duration: {formatDuration(activeJob.started_at, activeJob.completed_at)}</div>
              </div>
              <button
                onClick={() => setActiveJobId(null)}
                className="text-xs text-accent hover:underline mt-2 cursor-pointer"
              >
                Dismiss
              </button>
            </div>
          </div>
        )}

        {isFailed && activeJob && (
          <div className="flex items-start gap-4 py-2">
            <XCircle className="w-6 h-6 text-danger flex-shrink-0 mt-0.5" />
            <div>
              <div className="text-sm font-medium text-danger">Discovery failed</div>
              <div className="text-xs text-dim mt-1">{activeJob.error_message || "Unknown error"}</div>
              <button
                onClick={() => setActiveJobId(null)}
                className="text-xs text-accent hover:underline mt-2 cursor-pointer"
              >
                Dismiss
              </button>
            </div>
          </div>
        )}

        {error && !isRunning && (
          <div className="mt-3 text-sm text-danger bg-danger/5 border border-danger/20 rounded-lg px-4 py-2">
            {error}
          </div>
        )}
      </Card>

      {/* Pending jurisdictions for review */}
      {pending.length > 0 && (
        <div>
          <div className="text-xs font-semibold uppercase tracking-widest text-dim mb-3">
            Discovered Jurisdictions — Pending Review
          </div>
          <Card>
            <DataTable
              columns={pendingColumns}
              data={pending as unknown as PendingJurisdiction[]}
              loading={pendingLoading}
              emptyMessage="No pending jurisdictions"
            />
          </Card>
        </div>
      )}

      {/* Job history */}
      {allJobs.length > 0 && (
        <div>
          <div className="text-xs font-semibold uppercase tracking-widest text-dim mb-3">
            Discovery History
          </div>
          <Card>
            <DataTable
              columns={jobColumns}
              data={allJobs}
              loading={jobsLoading}
              emptyMessage="No discovery jobs yet"
            />
          </Card>
        </div>
      )}

      <ConfirmDialog
        open={showConfirm}
        title="Discover Sub-Jurisdictions"
        message={`This will use AI to search for all sub-jurisdictions in ${countryName} that levy their own accommodation taxes. This may take 2-3 minutes.`}
        confirmLabel="Start Discovery"
        onConfirm={handleRun}
        onCancel={() => setShowConfirm(false)}
      />
    </div>
  );
}
