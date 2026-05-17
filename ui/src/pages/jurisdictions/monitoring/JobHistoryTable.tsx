import { useNavigate } from "react-router-dom";
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
  const navigate = useNavigate();

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
    <Card>
      <DataTable
        columns={columns}
        data={jobs}
        loading={loading}
        onRowClick={(j) => navigate(`/app/agent-monitoring/runs/${j.id}`)}
        emptyMessage="No monitoring jobs yet"
      />
    </Card>
  );
}
