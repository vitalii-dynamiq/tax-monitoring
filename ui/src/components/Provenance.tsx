import { Link } from "react-router-dom";
import { ExternalLink, ScanSearch } from "lucide-react";
import { useRunMeta } from "../hooks/useRunMeta";
import { formatRelative } from "../lib/utils";

interface ProvenanceProps {
  sourceUrl?: string | null;
  authority?: string | null;
  legalReference?: string | null;
  confidence?: number | null;
  sourceQuote?: string | null;
  monitoringJobId?: number | null;
  createdBy?: string | null;
  /** When true, fetches the source run and renders model · cost · age inline. */
  showRunMeta?: boolean;
  className?: string;
}

/** Compact provenance block for AI-produced suggestions (drafts, pending jurisdictions, etc.).
 *
 *  - Source URL → external link
 *  - Authority + legal reference inline
 *  - Confidence bar (0..1)
 *  - Source quote in an italic blockquote
 *  - "From run #N →" link to the AgentRunDetail page (admin-only)
 */
export default function Provenance({
  sourceUrl,
  authority,
  legalReference,
  confidence,
  sourceQuote,
  monitoringJobId,
  createdBy,
  showRunMeta = false,
  className,
}: ProvenanceProps) {
  const runMeta = useRunMeta(showRunMeta ? monitoringJobId ?? null : null);
  const hasAny =
    sourceUrl || authority || legalReference || sourceQuote ||
    confidence !== null && confidence !== undefined ||
    monitoringJobId;

  if (!hasAny) return null;

  const pct =
    typeof confidence === "number"
      ? Math.max(0, Math.min(100, Math.round(confidence * 100)))
      : null;

  return (
    <div
      className={
        "border border-border rounded-md bg-surface/40 p-3 text-xs space-y-2 " +
        (className || "")
      }
    >
      <div className="flex items-center justify-between gap-2 flex-wrap">
        <span className="font-semibold uppercase tracking-wide text-dim">
          Provenance
        </span>
        {monitoringJobId && (
          <Link
            to={`/app/agent-monitoring/runs/${monitoringJobId}`}
            className="inline-flex items-center gap-1 text-accent hover:underline"
            title="See the agent run that produced this"
          >
            <ScanSearch className="w-3.5 h-3.5" />
            From run #{monitoringJobId} →
          </Link>
        )}
      </div>

      {showRunMeta && monitoringJobId && (
        <div className="text-dim">
          {runMeta === null ? (
            <span className="text-dim italic">Loading run meta…</span>
          ) : (
            <span>
              <span className="text-text">{runMeta.job_type}</span>
              {runMeta.model && (
                <span className="font-mono"> · {runMeta.model}</span>
              )}
              {runMeta.estimated_cost_usd && runMeta.estimated_cost_usd !== "0" && (
                <span> · ${runMeta.estimated_cost_usd}</span>
              )}
              {runMeta.started_at && (
                <span> · {formatRelative(runMeta.started_at)}</span>
              )}
            </span>
          )}
        </div>
      )}

      <div className="space-y-1.5">
        {sourceUrl && (
          <div className="flex items-center gap-1 text-text">
            <a
              href={sourceUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="text-accent hover:underline truncate"
            >
              {sourceUrl}
            </a>
            <ExternalLink className="w-3 h-3 flex-shrink-0 text-dim" />
          </div>
        )}
        {(authority || legalReference) && (
          <div className="text-muted">
            {authority && <span className="text-text">{authority}</span>}
            {authority && legalReference && <span className="text-dim"> · </span>}
            {legalReference && <span className="font-mono">{legalReference}</span>}
          </div>
        )}
        {createdBy && (
          <div className="text-dim">
            Created by <span className="font-mono text-muted">{createdBy}</span>
          </div>
        )}
      </div>

      {pct !== null && (
        <div>
          <div className="flex items-center justify-between text-dim mb-1">
            <span>AI confidence</span>
            <span className="tabular-nums text-muted">{pct}%</span>
          </div>
          <div className="h-1.5 bg-border rounded overflow-hidden">
            <div
              className={
                pct >= 80
                  ? "h-full bg-success"
                  : pct >= 50
                    ? "h-full bg-warning"
                    : "h-full bg-danger"
              }
              style={{ width: `${pct}%` }}
            />
          </div>
        </div>
      )}

      {sourceQuote && (
        <blockquote className="text-muted italic border-l-2 border-border pl-3 leading-relaxed">
          &ldquo;{sourceQuote}&rdquo;
        </blockquote>
      )}
    </div>
  );
}
