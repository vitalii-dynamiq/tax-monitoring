import { useState } from "react";
import PageHeader from "../components/PageHeader";
import PageTransition from "../components/PageTransition";
import Card from "../components/Card";
import DataTable, { type Column } from "../components/DataTable";
import Badge from "../components/Badge";
import { api, type AuditLogEntry } from "../lib/api";
import { useApi } from "../hooks/useApi";
import { formatDateTime } from "../lib/utils";

export default function AuditLog() {
  const [entityType, setEntityType] = useState("");

  const params: Record<string, string> = { limit: "200" };
  if (entityType) params.entity_type = entityType;

  const { data, loading } = useApi(() => api.audit.list(params), [entityType]);
  const [selected, setSelected] = useState<AuditLogEntry | null>(null);

  const columns: Column<AuditLogEntry>[] = [
    {
      key: "id",
      header: "ID",
      render: (r) => <span className="font-mono text-dim">#{r.id}</span>,
      className: "w-16",
      hideBelow: "sm",
    },
    {
      key: "entity_type",
      header: "Entity",
      render: (r) => <Badge value={r.entity_type} />,
    },
    {
      key: "entity_id",
      header: "Entity ID",
      render: (r) => <span className="font-mono font-medium text-accent">#{r.entity_id}</span>,
      className: "w-28",
      hideBelow: "md",
    },
    {
      key: "action",
      header: "Action",
      render: (r) => <span className="text-text font-medium">{r.action}</span>,
    },
    {
      key: "changed_by",
      header: "Changed By",
      render: (r) => <span className="text-muted">{r.changed_by || "system"}</span>,
    },
    {
      key: "change_source",
      header: "Source",
      render: (r) => <Badge value={r.change_source} />,
      hideBelow: "lg",
    },
    {
      key: "created_at",
      header: "Timestamp",
      render: (r) => (
        <span className="text-dim text-sm font-mono">{formatDateTime(r.created_at)}</span>
      ),
    },
  ];

  return (
    <PageTransition>
    <div className="p-4 sm:p-6 lg:p-10 max-w-[1400px]">
      <PageHeader
        title="Audit Log"
        description="Complete record of all changes for compliance and traceability"
      />

      <div className="flex flex-col sm:flex-row gap-3 mb-6">
        <select
          value={entityType}
          onChange={(e) => setEntityType(e.target.value)}
          className="input-field w-full sm:w-52"
        >
          <option value="">All entities</option>
          <option value="tax_rate">Tax Rate</option>
          <option value="tax_rule">Tax Rule</option>
          <option value="jurisdiction">Jurisdiction</option>
          <option value="detected_change">Detected Change</option>
          <option value="monitored_source">Monitored Source</option>
        </select>
      </div>

      <Card>
        <DataTable
          columns={columns}
          data={data || []}
          loading={loading}
          onRowClick={(r) => setSelected(selected?.id === r.id ? null : r)}
          emptyMessage="No audit entries found"
        />
      </Card>

      {selected && (
        <Card className="mt-5 p-6">
          <div className="text-xs font-semibold uppercase tracking-widest text-dim mb-4">
            Audit Entry <span className="text-accent font-mono">#{selected.id}</span> — {selected.entity_type} <span className="text-accent font-mono">#{selected.entity_id}</span>
          </div>
          {selected.change_reason && (
            <div className="mb-5">
              <div className="text-xs font-semibold uppercase tracking-widest text-dim mb-2">
                Reason
              </div>
              <div className="text-sm text-muted bg-surface rounded-lg p-4 border border-border">
                {selected.change_reason}
              </div>
            </div>
          )}
          <div className="grid grid-cols-2 gap-5">
            {selected.old_values && Object.keys(selected.old_values).length > 0 && (
              <div>
                <div className="text-xs font-semibold uppercase tracking-widest text-dim mb-2">
                  Previous Values
                </div>
                <pre className="bg-surface rounded-lg p-5 font-mono text-sm text-muted overflow-x-auto whitespace-pre-wrap border border-border">
{JSON.stringify(selected.old_values, null, 2)}</pre>
              </div>
            )}
            {selected.new_values && Object.keys(selected.new_values).length > 0 && (
              <div>
                <div className="text-xs font-semibold uppercase tracking-widest text-dim mb-2">
                  New Values
                </div>
                <pre className="bg-surface rounded-lg p-5 font-mono text-sm text-muted overflow-x-auto whitespace-pre-wrap border border-border">
{JSON.stringify(selected.new_values, null, 2)}</pre>
              </div>
            )}
          </div>
        </Card>
      )}
    </div>
    </PageTransition>
  );
}
