import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import Card from "../Card";
import Badge from "../Badge";
import { api, type ProducedEntities } from "../../lib/api";
import { formatDateTime, formatPercent } from "../../lib/utils";

interface RunProducedTabProps {
  jobId: number;
}

function Section({
  title,
  count,
  children,
}: {
  title: string;
  count: number;
  children: React.ReactNode;
}) {
  return (
    <Card className="overflow-hidden">
      <div className="flex items-center justify-between px-4 py-3 border-b border-border">
        <h3 className="text-sm font-semibold text-text">{title}</h3>
        <span className="text-xs text-dim tabular-nums">{count}</span>
      </div>
      {count === 0 ? (
        <div className="px-4 py-6 text-sm text-dim text-center">— none produced —</div>
      ) : (
        children
      )}
    </Card>
  );
}

export default function RunProducedTab({ jobId }: RunProducedTabProps) {
  const [data, setData] = useState<ProducedEntities | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    api.monitoring
      .getJobProduced(jobId)
      .then((d) => !cancelled && setData(d))
      .catch((e) => !cancelled && setError(e.message));
    return () => {
      cancelled = true;
    };
  }, [jobId]);

  if (error) {
    return <Card className="p-6 text-sm text-danger">Failed: {error}</Card>;
  }
  if (!data) {
    return <Card className="p-6 text-muted">Loading produced entities…</Card>;
  }

  return (
    <div className="space-y-4">
      <Section title="New jurisdictions" count={data.jurisdictions.length}>
        <table className="w-full text-sm">
          <thead className="text-left text-xs uppercase tracking-wide text-dim">
            <tr>
              <th className="px-4 py-2 font-semibold">Code</th>
              <th className="px-4 py-2 font-semibold">Name</th>
              <th className="px-4 py-2 font-semibold">Type</th>
              <th className="px-4 py-2 font-semibold">Status</th>
              <th className="px-4 py-2 font-semibold">Created</th>
            </tr>
          </thead>
          <tbody>
            {data.jurisdictions.map((j) => (
              <tr key={j.id} className="border-t border-border/60 hover:bg-hover/30">
                <td className="px-4 py-2 font-mono">
                  <Link
                    to={`/app/jurisdictions/${j.code}`}
                    className="text-accent hover:underline"
                  >
                    {j.code}
                  </Link>
                </td>
                <td className="px-4 py-2">{j.name}</td>
                <td className="px-4 py-2">
                  <Badge value={j.jurisdiction_type} />
                </td>
                <td className="px-4 py-2">
                  <Badge value={j.status} />
                </td>
                <td className="px-4 py-2 text-dim text-xs whitespace-nowrap">
                  {formatDateTime(j.created_at)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </Section>

      <Section title="Draft tax rates" count={data.tax_rates.length}>
        <table className="w-full text-sm">
          <thead className="text-left text-xs uppercase tracking-wide text-dim">
            <tr>
              <th className="px-4 py-2 font-semibold">Jurisdiction</th>
              <th className="px-4 py-2 font-semibold">Category</th>
              <th className="px-4 py-2 font-semibold">Type</th>
              <th className="px-4 py-2 font-semibold">Value</th>
              <th className="px-4 py-2 font-semibold">Status</th>
              <th className="px-4 py-2 font-semibold">Created</th>
            </tr>
          </thead>
          <tbody>
            {data.tax_rates.map((r) => (
              <tr key={r.id} className="border-t border-border/60 hover:bg-hover/30">
                <td className="px-4 py-2 font-mono">{r.jurisdiction_code || "—"}</td>
                <td className="px-4 py-2 font-mono text-xs">{r.tax_category_code || "—"}</td>
                <td className="px-4 py-2">
                  <Badge value={r.rate_type} />
                </td>
                <td className="px-4 py-2 tabular-nums">
                  {r.rate_value === null
                    ? "—"
                    : r.rate_type === "percentage"
                      ? formatPercent(r.rate_value)
                      : r.rate_value}
                </td>
                <td className="px-4 py-2">
                  <Badge value={r.status} />
                </td>
                <td className="px-4 py-2 text-dim text-xs whitespace-nowrap">
                  {formatDateTime(r.created_at)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </Section>

      <Section title="Draft tax rules" count={data.tax_rules.length}>
        <table className="w-full text-sm">
          <thead className="text-left text-xs uppercase tracking-wide text-dim">
            <tr>
              <th className="px-4 py-2 font-semibold">Jurisdiction</th>
              <th className="px-4 py-2 font-semibold">Type</th>
              <th className="px-4 py-2 font-semibold">Name</th>
              <th className="px-4 py-2 font-semibold">Status</th>
              <th className="px-4 py-2 font-semibold">Created</th>
            </tr>
          </thead>
          <tbody>
            {data.tax_rules.map((r) => (
              <tr key={r.id} className="border-t border-border/60 hover:bg-hover/30">
                <td className="px-4 py-2 font-mono">{r.jurisdiction_code || "—"}</td>
                <td className="px-4 py-2">
                  <Badge value={r.rule_type} />
                </td>
                <td className="px-4 py-2">{r.name}</td>
                <td className="px-4 py-2">
                  <Badge value={r.status} />
                </td>
                <td className="px-4 py-2 text-dim text-xs whitespace-nowrap">
                  {formatDateTime(r.created_at)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </Section>

      <Section title="Detected changes" count={data.detected_changes.length}>
        <table className="w-full text-sm">
          <thead className="text-left text-xs uppercase tracking-wide text-dim">
            <tr>
              <th className="px-4 py-2 font-semibold">Jurisdiction</th>
              <th className="px-4 py-2 font-semibold">Change type</th>
              <th className="px-4 py-2 font-semibold">Review</th>
              <th className="px-4 py-2 font-semibold">Confidence</th>
              <th className="px-4 py-2 font-semibold">Created</th>
            </tr>
          </thead>
          <tbody>
            {data.detected_changes.map((c) => (
              <tr key={c.id} className="border-t border-border/60 hover:bg-hover/30">
                <td className="px-4 py-2 font-mono">{c.jurisdiction_code || "—"}</td>
                <td className="px-4 py-2">
                  <Badge value={c.change_type} />
                </td>
                <td className="px-4 py-2">
                  <Badge value={c.review_status} />
                </td>
                <td className="px-4 py-2 tabular-nums">
                  {(c.confidence * 100).toFixed(0)}%
                </td>
                <td className="px-4 py-2 text-dim text-xs whitespace-nowrap">
                  {formatDateTime(c.created_at)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </Section>
    </div>
  );
}
