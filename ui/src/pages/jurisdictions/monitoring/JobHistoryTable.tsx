import { useState } from "react";
import Card from "../../../components/Card";
import Badge from "../../../components/Badge";
import DataTable, { type Column } from "../../../components/DataTable";
import { type MonitoringJob } from "../../../lib/api";
import { formatDateTime, formatDuration } from "../../../lib/utils";

interface JobHistoryTableProps {
  jobs: MonitoringJob[];
  loading: boolean;
}

export default function JobHistoryTable({ jobs, loading }: JobHistoryTableProps) {
  const [selected, setSelected] = useState<MonitoringJob | null>(null);

  const columns: Column<MonitoringJob>[] = [
    {
      key: "id",
      header: "ID",
      render: (j) => <span className="font-mono text-dim">#{j.id}</span>,
      className: "w-16",
    },
    {
      key: "status",
      header: "Status",
      render: (j) => (
        <div className="flex items-center gap-2">
          <Badge value={j.status} />
          {j.status === "running" && (
            <span className="w-2 h-2 bg-accent rounded-full animate-pulse" />
          )}
        </div>
      ),
    },
    {
      key: "trigger",
      header: "Trigger",
      render: (j) => <Badge value={j.trigger_type} />,
    },
    {
      key: "started",
      header: "Started",
      render: (j) => (
        <span className="text-dim text-sm">{formatDateTime(j.started_at)}</span>
      ),
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
      key: "changes",
      header: "Changes",
      render: (j) => (
        <span
          className={`font-mono font-medium ${
            j.changes_detected > 0 ? "text-accent" : "text-dim"
          }`}
        >
          {j.changes_detected}
        </span>
      ),
    },
  ];

  return (
    <div>
      <Card>
        <DataTable
          columns={columns}
          data={jobs}
          loading={loading}
          onRowClick={(j) => setSelected(selected?.id === j.id ? null : j)}
          emptyMessage="No monitoring jobs yet"
        />
      </Card>

      {selected && (
        <Card className="mt-5 p-6">
          <div className="text-xs font-semibold uppercase tracking-widest text-dim mb-4">
            Job <span className="text-accent font-mono">#{selected.id}</span> &mdash; Details
          </div>

          <div className="grid grid-cols-2 gap-4 text-sm mb-4">
            <div>
              <span className="text-dim">Triggered by:</span>{" "}
              <span className="text-text">{selected.triggered_by}</span>
            </div>
            <div>
              <span className="text-dim">Created:</span>{" "}
              <span className="text-text">{formatDateTime(selected.created_at)}</span>
            </div>
          </div>

          {selected.error_message && (
            <div className="mb-4">
              <div className="text-xs font-semibold uppercase tracking-widest text-danger mb-2">
                Error
              </div>
              <div className="text-sm text-danger bg-danger/5 border border-danger/20 rounded-lg p-4">
                {selected.error_message}
              </div>
            </div>
          )}

          {selected.result_summary && (
            <div>
              <div className="text-xs font-semibold uppercase tracking-widest text-dim mb-2">
                Result Summary
              </div>
              <pre className="bg-surface rounded-lg p-5 font-mono text-sm text-muted overflow-x-auto whitespace-pre-wrap border border-border">
                {JSON.stringify(selected.result_summary, null, 2)}
              </pre>
            </div>
          )}
        </Card>
      )}
    </div>
  );
}
