import { useState, useMemo } from "react";
import Card from "../../components/Card";
import Badge from "../../components/Badge";
import StatCard from "../../components/StatCard";
import DataTable, { type Column } from "../../components/DataTable";
import { api, type DetectedChange } from "../../lib/api";
import { useApi } from "../../hooks/useApi";
import { useToast } from "../../hooks/useToast";
import { formatDateTime } from "../../lib/utils";
import { CheckCircle2, XCircle } from "lucide-react";

type ReviewFilter = "all" | "pending" | "approved" | "rejected";

export default function ChangesTab({ jurisdictionCode }: { jurisdictionCode: string }) {
  const { toast } = useToast();
  const [reviewFilter, setReviewFilter] = useState<ReviewFilter>("all");
  const [selected, setSelected] = useState<DetectedChange | null>(null);
  const [reviewNotes, setReviewNotes] = useState("");
  const [reviewLoading, setReviewLoading] = useState(false);

  const { data, loading, refetch } = useApi(
    () => api.monitoring.changes({ jurisdiction_code: jurisdictionCode, limit: "500" }),
    [jurisdictionCode]
  );

  const changes = data || [];
  const pendingCount = changes.filter((c) => c.review_status === "pending").length;
  const avgConfidence = changes.length > 0
    ? changes.reduce((sum, c) => sum + c.confidence, 0) / changes.length
    : 0;

  const filtered = useMemo(() => {
    if (reviewFilter === "all") return changes;
    return changes.filter((c) => c.review_status === reviewFilter);
  }, [changes, reviewFilter]);

  const handleReview = async (changeId: number, status: "approved" | "rejected") => {
    setReviewLoading(true);
    try {
      await api.monitoring.reviewChange(changeId, {
        review_status: status,
        reviewed_by: "ui_user",
        review_notes: reviewNotes || undefined,
      });
      toast(status === "approved" ? "Change approved successfully" : "Change rejected", "success");
      setReviewNotes("");
      setSelected(null);
      refetch();
    } catch (e) {
      console.error("Review failed:", e);
      toast("Failed to review change", "error");
    } finally {
      setReviewLoading(false);
    }
  };

  const columns: Column<DetectedChange>[] = [
    {
      key: "id",
      header: "ID",
      render: (r) => <span className="font-mono text-dim">#{r.id}</span>,
      className: "w-16",
    },
    {
      key: "type",
      header: "Change Type",
      render: (r) => <span className="text-text">{r.change_type}</span>,
    },
    {
      key: "confidence",
      header: "Confidence",
      render: (r) => (
        <div className="flex items-center gap-2">
          <div className="w-16 h-1.5 bg-surface rounded-full overflow-hidden border border-border">
            <div
              className="h-full bg-accent rounded-full"
              style={{ width: `${r.confidence * 100}%` }}
            />
          </div>
          <span className="font-mono font-medium text-sm">{(r.confidence * 100).toFixed(0)}%</span>
        </div>
      ),
    },
    {
      key: "review",
      header: "Review",
      render: (r) => <Badge value={r.review_status} />,
    },
    {
      key: "created",
      header: "Detected",
      render: (r) => (
        <span className="text-dim text-sm">{formatDateTime(r.created_at)}</span>
      ),
    },
  ];

  const filters: { key: ReviewFilter; label: string }[] = [
    { key: "all", label: "All" },
    { key: "pending", label: "Pending" },
    { key: "approved", label: "Approved" },
    { key: "rejected", label: "Rejected" },
  ];

  return (
    <div className="space-y-5">
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-5">
        <StatCard label="Total Changes" value={changes.length} sub="Detected all time" />
        <StatCard
          label="Pending Review"
          value={pendingCount}
          accent={pendingCount > 0 ? "warning" : "default"}
          sub="Needs attention"
        />
        <StatCard
          label="Avg. Confidence"
          value={`${(avgConfidence * 100).toFixed(0)}%`}
          sub="Detection accuracy"
        />
      </div>

      <div className="flex gap-1 bg-surface rounded-lg p-1 w-fit border border-border">
        {filters.map((f) => (
          <button
            key={f.key}
            onClick={() => { setReviewFilter(f.key); setSelected(null); }}
            className={`px-4 py-2 text-sm font-medium rounded-md cursor-pointer transition-all ${
              reviewFilter === f.key
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
          data={filtered}
          loading={loading}
          onRowClick={(r) => setSelected(selected?.id === r.id ? null : r)}
          emptyMessage="No changes detected yet"
        />
      </Card>

      {selected && (
        <Card className="mt-5 p-6">
          <div className="flex items-center justify-between mb-4">
            <div className="text-xs font-semibold uppercase tracking-widest text-dim">
              Change <span className="text-accent font-mono">#{selected.id}</span> &mdash;{" "}
              <Badge value={selected.review_status} className="ml-1" />
            </div>
            <div className="text-xs text-dim">
              {selected.reviewed_by && (
                <span>Reviewed by {selected.reviewed_by}</span>
              )}
            </div>
          </div>

          {/* Evidence: source quote */}
          {selected.source_quote && (
            <div className="mb-5">
              <div className="text-xs font-semibold uppercase tracking-widest text-dim mb-2">
                Source Quote
              </div>
              <div className="text-sm text-muted italic bg-surface rounded-lg p-4 border border-border">
                &ldquo;{selected.source_quote}&rdquo;
              </div>
            </div>
          )}

          {/* Evidence: source URL */}
          {selected.source_snapshot_url && (
            <div className="mb-5">
              <div className="text-xs font-semibold uppercase tracking-widest text-dim mb-2">
                Source URL
              </div>
              <a
                href={selected.source_snapshot_url}
                target="_blank"
                rel="noopener noreferrer"
                className="text-sm text-accent hover:underline break-all"
              >
                {selected.source_snapshot_url}
              </a>
            </div>
          )}

          {/* Confidence bar */}
          <div className="mb-5">
            <div className="text-xs font-semibold uppercase tracking-widest text-dim mb-2">
              Confidence
            </div>
            <div className="flex items-center gap-3">
              <div className="flex-1 h-2 bg-surface rounded-full overflow-hidden border border-border">
                <div
                  className="h-full bg-accent rounded-full transition-all"
                  style={{ width: `${selected.confidence * 100}%` }}
                />
              </div>
              <span className="text-sm font-mono font-medium">
                {(selected.confidence * 100).toFixed(0)}%
              </span>
            </div>
          </div>

          {/* Extracted data */}
          <div className="mb-5">
            <div className="text-xs font-semibold uppercase tracking-widest text-dim mb-2">
              Extracted Data
            </div>
            <pre className="bg-surface rounded-lg p-5 font-mono text-sm text-muted overflow-x-auto whitespace-pre-wrap border border-border">
{JSON.stringify(selected.extracted_data, null, 2)}</pre>
          </div>

          {/* Review notes from previous review */}
          {selected.review_notes && (
            <div className="mb-5">
              <div className="text-xs font-semibold uppercase tracking-widest text-dim mb-2">
                Review Notes
              </div>
              <div className="text-sm text-muted bg-surface rounded-lg p-4 border border-border">
                {selected.review_notes}
              </div>
            </div>
          )}

          {/* Review actions — only for pending changes */}
          {selected.review_status === "pending" && (
            <div className="border-t border-border pt-5 mt-5">
              <div className="text-xs font-semibold uppercase tracking-widest text-dim mb-3">
                Review Actions
              </div>
              <textarea
                value={reviewNotes}
                onChange={(e) => setReviewNotes(e.target.value)}
                placeholder="Optional review notes..."
                rows={2}
                className="input-field w-full text-sm mb-3 resize-none"
              />
              <div className="flex gap-3">
                <button
                  onClick={() => handleReview(selected.id, "approved")}
                  disabled={reviewLoading}
                  className="flex items-center gap-2 px-4 py-2 text-sm font-medium rounded-lg bg-success/10 text-success border border-success/25 hover:bg-success/20 cursor-pointer transition-colors disabled:opacity-50"
                >
                  <CheckCircle2 className="w-4 h-4" />
                  Approve
                </button>
                <button
                  onClick={() => handleReview(selected.id, "rejected")}
                  disabled={reviewLoading}
                  className="flex items-center gap-2 px-4 py-2 text-sm font-medium rounded-lg bg-danger/10 text-danger border border-danger/25 hover:bg-danger/20 cursor-pointer transition-colors disabled:opacity-50"
                >
                  <XCircle className="w-4 h-4" />
                  Reject
                </button>
              </div>
            </div>
          )}
        </Card>
      )}
    </div>
  );
}
