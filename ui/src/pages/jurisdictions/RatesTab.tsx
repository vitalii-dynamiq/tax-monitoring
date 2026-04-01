import { useState, useMemo } from "react";
import Card from "../../components/Card";
import Badge from "../../components/Badge";
import DataTable, { type Column } from "../../components/DataTable";
import { api, type TaxRate } from "../../lib/api";
import { useApi } from "../../hooks/useApi";
import { formatDate } from "../../lib/utils";

type StatusFilter = "all" | "active" | "scheduled" | "history";

export default function RatesTab({ jurisdictionCode }: { jurisdictionCode: string }) {
  const [statusFilter, setStatusFilter] = useState<StatusFilter>("all");
  const [selectedRate, setSelectedRate] = useState<TaxRate | null>(null);

  const { data, loading } = useApi(
    () => api.rates.list({ jurisdiction_code: jurisdictionCode, limit: "500" }),
    [jurisdictionCode]
  );

  const filteredRates = useMemo(() => {
    const rates = data || [];
    switch (statusFilter) {
      case "active":
        return rates.filter((r) => r.status === "active");
      case "scheduled":
        return rates.filter((r) => ["scheduled", "approved", "draft"].includes(r.status));
      case "history":
        return rates.filter((r) => ["superseded", "rejected"].includes(r.status));
      default:
        return rates;
    }
  }, [data, statusFilter]);

  const counts = useMemo(() => {
    const rates = data || [];
    return {
      all: rates.length,
      active: rates.filter((r) => r.status === "active").length,
      scheduled: rates.filter((r) => ["scheduled", "approved", "draft"].includes(r.status)).length,
      history: rates.filter((r) => ["superseded", "rejected"].includes(r.status)).length,
    };
  }, [data]);

  const columns: Column<TaxRate>[] = [
    {
      key: "id",
      header: "ID",
      render: (r) => <span className="font-mono text-dim">#{r.id}</span>,
      className: "w-16",
    },
    {
      key: "category",
      header: "Category",
      render: (r) => <span className="text-text">{r.tax_category_code}</span>,
    },
    {
      key: "type",
      header: "Type",
      render: (r) => <Badge value={r.rate_type} />,
    },
    {
      key: "value",
      header: "Rate",
      render: (r) => (
        <span className="font-mono font-semibold text-text">
          {r.rate_type === "percentage" && r.rate_value != null
            ? `${(r.rate_value * 100).toFixed(3)}%`
            : r.rate_type === "flat" && r.rate_value != null
              ? `${r.currency_code || ""} ${r.rate_value}`
              : "Tiered"}
        </span>
      ),
    },
    {
      key: "order",
      header: "Order",
      render: (r) => <span className="font-mono text-dim">{r.calculation_order}</span>,
      className: "w-20",
    },
    {
      key: "effective",
      header: "Effective",
      render: (r) => (
        <div className="text-sm">
          <div className="text-muted">{formatDate(r.effective_start)}</div>
          {r.effective_end && <div className="text-dim">&rarr; {formatDate(r.effective_end)}</div>}
        </div>
      ),
    },
    {
      key: "status",
      header: "Status",
      render: (r) => <Badge value={r.status} />,
    },
  ];

  const filters: { key: StatusFilter; label: string }[] = [
    { key: "all", label: `All (${counts.all})` },
    { key: "active", label: `Active (${counts.active})` },
    { key: "scheduled", label: `Scheduled (${counts.scheduled})` },
    { key: "history", label: `History (${counts.history})` },
  ];

  return (
    <div className="space-y-5">
      <div className="flex gap-1 bg-surface rounded-lg p-1 w-fit border border-border">
        {filters.map((f) => (
          <button
            key={f.key}
            onClick={() => { setStatusFilter(f.key); setSelectedRate(null); }}
            className={`px-4 py-2 text-sm font-medium rounded-md cursor-pointer transition-all ${
              statusFilter === f.key
                ? "bg-card text-text shadow-sm border border-border"
                : "text-dim hover:text-muted"
            }`}
          >
            {f.label}
          </button>
        ))}
      </div>

      <Card>
        <DataTable
          columns={columns}
          data={filteredRates}
          loading={loading}
          onRowClick={(r) => setSelectedRate(selectedRate?.id === r.id ? null : r)}
          emptyMessage="No tax rates found"
        />
      </Card>

      {selectedRate && (
        <Card className="mt-5">
          <div className="px-6 py-4 border-b border-border flex items-center justify-between">
            <span className="text-base font-semibold text-text">
              Rate <span className="font-mono text-accent">#{selectedRate.id}</span> &mdash; {selectedRate.tax_category_code}
            </span>
            <Badge value={selectedRate.status} />
          </div>
          <div className="grid grid-cols-2 gap-x-8 gap-y-5 p-6">
            <Detail label="Legal Reference" value={selectedRate.legal_reference} />
            <Detail label="Authority" value={selectedRate.authority_name} />
            <Detail label="Source URL" value={selectedRate.source_url} link />
            <Detail label="Legal URI" value={selectedRate.legal_uri} />
            <Detail label="Enacted Date" value={formatDate(selectedRate.enacted_date)} />
            <Detail label="Created By" value={selectedRate.created_by} />
            <Detail label="Reviewed By" value={selectedRate.reviewed_by} />
            <Detail label="Reviewed At" value={formatDate(selectedRate.reviewed_at)} />
            {selectedRate.base_includes && selectedRate.base_includes.length > 0 && (
              <Detail label="Base Includes" value={selectedRate.base_includes.join(", ")} />
            )}
            {selectedRate.tiers && selectedRate.tiers.length > 0 && (
              <div className="col-span-2">
                <div className="text-xs font-semibold uppercase tracking-widest text-dim mb-2">
                  Tiers ({selectedRate.tier_type})
                </div>
                <div className="overflow-x-auto border border-border rounded-lg">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="bg-surface text-dim text-xs uppercase tracking-widest">
                        <th className="px-4 py-2.5 text-left font-semibold">Range</th>
                        <th className="px-4 py-2.5 text-right font-semibold">
                          {selectedRate.tier_type === "single_amount" ? "Amount" : "Rate"}
                        </th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-border">
                      {selectedRate.tiers.map((tier, i) => (
                        <tr key={i} className="hover:bg-surface/50">
                          <td className="px-4 py-2 font-mono text-muted">
                            {String(tier.min ?? 0)}
                            {tier.max != null ? ` - ${String(tier.max)}` : "+"}
                          </td>
                          <td className="px-4 py-2 font-mono text-text text-right font-medium">
                            {selectedRate.tier_type === "single_amount"
                              ? `${selectedRate.currency_code || ""} ${tier.value ?? "\u2014"}`
                              : tier.rate != null
                                ? `${(Number(tier.rate) * 100).toFixed(2)}%`
                                : "\u2014"}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}
          </div>
        </Card>
      )}
    </div>
  );
}

function Detail({
  label,
  value,
  link,
}: {
  label: string;
  value: string | null | undefined;
  link?: boolean;
}) {
  return (
    <div>
      <div className="text-xs font-semibold uppercase tracking-widest text-dim mb-1">{label}</div>
      {link && value ? (
        <a
          href={value}
          target="_blank"
          rel="noopener noreferrer"
          className="text-sm text-accent hover:underline break-all"
        >
          {value}
        </a>
      ) : (
        <div className="text-sm text-text">{value || "\u2014"}</div>
      )}
    </div>
  );
}
