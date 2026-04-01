import React, { useState } from "react";
import Card from "../../components/Card";
import Badge from "../../components/Badge";
import DataTable, { type Column } from "../../components/DataTable";
import { api, type TaxRule } from "../../lib/api";
import { useApi } from "../../hooks/useApi";
import { formatDate } from "../../lib/utils";

export default function RulesTab({ jurisdictionCode }: { jurisdictionCode: string }) {
  const [typeFilter, setTypeFilter] = useState("");
  const [selected, setSelected] = useState<TaxRule | null>(null);

  const params: Record<string, string> = { jurisdiction_code: jurisdictionCode, limit: "500" };
  if (typeFilter) params.rule_type = typeFilter;

  const { data, loading } = useApi(() => api.rules.list(params), [jurisdictionCode, typeFilter]);

  const columns: Column<TaxRule>[] = [
    {
      key: "id",
      header: "ID",
      render: (r) => <span className="font-mono text-dim">#{r.id}</span>,
      className: "w-16",
    },
    {
      key: "name",
      header: "Name",
      render: (r) => (
        <div>
          <div className="font-medium text-text">{r.name}</div>
          {r.description && (
            <div className="text-xs text-dim mt-0.5 line-clamp-1">{r.description}</div>
          )}
        </div>
      ),
    },
    {
      key: "type",
      header: "Type",
      render: (r) => <Badge value={r.rule_type} />,
    },
    {
      key: "priority",
      header: "Priority",
      render: (r) => <span className="font-mono text-muted">{r.priority}</span>,
      className: "w-24",
    },
    {
      key: "rate",
      header: "Rate ID",
      render: (r) => (
        <span className="font-mono text-dim">{r.tax_rate_id ? `#${r.tax_rate_id}` : "\u2014"}</span>
      ),
      className: "w-24",
    },
    {
      key: "effective",
      header: "Effective",
      render: (r) => <span className="text-dim text-sm">{formatDate(r.effective_start)}</span>,
    },
    {
      key: "status",
      header: "Status",
      render: (r) => <Badge value={r.status} />,
    },
  ];

  return (
    <div className="space-y-5">
      <div className="flex gap-3">
        <select
          value={typeFilter}
          onChange={(e) => { setTypeFilter(e.target.value); setSelected(null); }}
          className="input-field w-44"
        >
          <option value="">All types</option>
          <option value="condition">Condition</option>
          <option value="exemption">Exemption</option>
          <option value="reduction">Reduction</option>
          <option value="surcharge">Surcharge</option>
          <option value="cap">Cap</option>
          <option value="override">Override</option>
          <option value="threshold">Threshold</option>
        </select>
      </div>

      <Card>
        <DataTable
          columns={columns}
          data={data || []}
          loading={loading}
          onRowClick={(r) => setSelected(selected?.id === r.id ? null : r)}
          emptyMessage="No tax rules found"
        />
      </Card>

      {selected && (
        <Card className="mt-5">
          <div className="px-6 py-4 border-b border-border flex items-center justify-between">
            <span className="text-base font-semibold text-text">
              Rule <span className="font-mono text-accent">#{selected.id}</span> &mdash; {selected.name}
            </span>
            <Badge value={selected.rule_type} />
          </div>
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-5 p-6">
            <div>
              <div className="text-xs font-semibold uppercase tracking-widest text-dim mb-2">
                Conditions
              </div>
              <div className="bg-surface rounded-lg p-5 border border-border space-y-2">
                {selected.conditions && Object.keys(selected.conditions).length > 0
                  ? formatConditions(selected.conditions)
                  : <span className="text-sm text-dim">No conditions (always applies)</span>}
              </div>
            </div>
            <div>
              <div className="text-xs font-semibold uppercase tracking-widest text-dim mb-2">
                Action
              </div>
              <div className="bg-surface rounded-lg p-5 border border-border space-y-2">
                {selected.action && Object.keys(selected.action).length > 0
                  ? formatAction(selected.action, selected.rule_type)
                  : <span className="text-sm text-dim">No action defined</span>}
              </div>
            </div>
            {selected.description && (
              <div className="lg:col-span-2">
                <div className="text-xs font-semibold uppercase tracking-widest text-dim mb-1">
                  Description
                </div>
                <div className="text-sm text-text">{selected.description}</div>
              </div>
            )}
            {selected.legal_reference && (
              <div className="lg:col-span-2">
                <div className="text-xs font-semibold uppercase tracking-widest text-dim mb-1">
                  Legal Reference
                </div>
                <div className="text-sm text-text">{selected.legal_reference}</div>
              </div>
            )}
          </div>
        </Card>
      )}
    </div>
  );
}

// ─── Condition / Action Formatting ──────────────────────────

const OP_LABELS: Record<string, string> = {
  "==": "equals",
  "!=": "does not equal",
  ">": "is greater than",
  ">=": "is at least",
  "<": "is less than",
  "<=": "is at most",
  in: "is one of",
  not_in: "is not one of",
  between: "is between",
};

function formatConditions(conditions: Record<string, unknown>): React.JSX.Element {
  const items: React.JSX.Element[] = [];

  const andList = conditions.AND ?? conditions.and;
  const orList = conditions.OR ?? conditions.or;

  if (Array.isArray(andList)) {
    andList.forEach((c: Record<string, unknown>, i: number) => {
      const cond = c as { field?: string; operator?: string; value?: unknown };
      if (cond.field && cond.operator) {
        const opLabel = OP_LABELS[cond.operator] || cond.operator;
        const val = Array.isArray(cond.value) ? cond.value.join(", ") : String(cond.value ?? "");
        items.push(
          <div key={i} className="flex items-center gap-2 text-sm">
            {i > 0 && <span className="text-xs font-semibold text-accent">AND</span>}
            <span className="font-mono text-accent">{cond.field}</span>
            <span className="text-dim">{opLabel}</span>
            <span className="font-mono font-medium text-text">{val}</span>
          </div>
        );
      }
    });
  } else if (Array.isArray(orList)) {
    orList.forEach((c: Record<string, unknown>, i: number) => {
      const cond = c as { field?: string; operator?: string; value?: unknown };
      if (cond.field && cond.operator) {
        const opLabel = OP_LABELS[cond.operator] || cond.operator;
        const val = Array.isArray(cond.value) ? cond.value.join(", ") : String(cond.value ?? "");
        items.push(
          <div key={i} className="flex items-center gap-2 text-sm">
            {i > 0 && <span className="text-xs font-semibold text-warning">OR</span>}
            <span className="font-mono text-accent">{cond.field}</span>
            <span className="text-dim">{opLabel}</span>
            <span className="font-mono font-medium text-text">{val}</span>
          </div>
        );
      }
    });
  }

  if (items.length === 0) {
    return (
      <pre className="font-mono text-sm text-muted whitespace-pre-wrap">
        {JSON.stringify(conditions, null, 2)}
      </pre>
    );
  }

  return <>{items}</>;
}

const ACTION_LABELS: Record<string, string> = {
  reduction_pct: "Reduce by",
  cap_nights: "Cap at nights",
  cap_amount: "Cap at amount",
  surcharge_rate: "Surcharge rate",
  min_amount: "Minimum amount",
  override_rate: "Override rate to",
  exempt: "Full exemption",
};

function formatAction(action: Record<string, unknown>, ruleType: string): React.JSX.Element {
  const items: React.JSX.Element[] = [];

  for (const [key, value] of Object.entries(action)) {
    const label = ACTION_LABELS[key] || key.replace(/_/g, " ");
    let displayValue = String(value);

    if (key === "reduction_pct" && typeof value === "number") {
      displayValue = `${(value * 100).toFixed(0)}%`;
    } else if (key === "surcharge_rate" && typeof value === "number") {
      displayValue = `${(value * 100).toFixed(1)}%`;
    } else if (key === "exempt" && value === true) {
      displayValue = "Yes";
    }

    items.push(
      <div key={key} className="flex items-center gap-2 text-sm">
        <span className="text-dim">{label}:</span>
        <span className="font-mono font-medium text-text">{displayValue}</span>
      </div>
    );
  }

  if (items.length === 0) {
    if (ruleType === "exemption") {
      return <div className="text-sm text-text">Full exemption (100% reduction)</div>;
    }
    return <span className="text-sm text-dim">No action parameters</span>;
  }

  return <>{items}</>;
}
