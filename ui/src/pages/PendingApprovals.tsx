import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { CheckCircle2, CheckCheck, ChevronDown, ChevronRight, XCircle } from "lucide-react";
import PageHeader from "../components/PageHeader";
import Card from "../components/Card";
import Badge from "../components/Badge";
import EmptyState from "../components/EmptyState";
import StatCard from "../components/StatCard";
import { useApi } from "../hooks/useApi";
import { useAuth } from "../hooks/useAuth";
import { useToast } from "../hooks/useToast";
import {
  api,
  type PendingSummaryRow,
  type TaxRate,
  type TaxRule,
} from "../lib/api";
import { formatDate } from "../lib/utils";

export default function PendingApprovals() {
  const { isAdmin } = useAuth();
  const { toast } = useToast();
  const navigate = useNavigate();
  const [search, setSearch] = useState("");
  const [batchFilter, setBatchFilter] = useState<string>("");
  const [expanded, setExpanded] = useState<Set<string>>(new Set());
  const [busyCode, setBusyCode] = useState<string | null>(null);

  const { data, loading, error, refetch } = useApi(() => api.approvals.summary(), []);

  const rows = useMemo(() => data?.rows || [], [data]);

  const allTags = useMemo(() => {
    const tags = new Set<string>();
    rows.forEach((r) => r.created_by_tags.forEach((t) => tags.add(t)));
    return Array.from(tags).sort();
  }, [rows]);

  const filtered = useMemo(() => {
    return rows.filter((r) => {
      if (batchFilter && !r.created_by_tags.includes(batchFilter)) return false;
      if (search) {
        const q = search.toLowerCase();
        if (
          !r.jurisdiction_code.toLowerCase().includes(q) &&
          !r.jurisdiction_name.toLowerCase().includes(q)
        ) {
          return false;
        }
      }
      return true;
    });
  }, [rows, search, batchFilter]);

  if (!isAdmin) {
    return (
      <div className="p-6 sm:p-10 max-w-4xl mx-auto">
        <Card className="p-8 text-center">
          <h2 className="text-lg font-semibold text-text mb-2">Admin access required</h2>
          <p className="text-muted mb-4">This page is only available to administrators.</p>
          <button className="btn-primary" onClick={() => navigate("/app")}>
            Back to Dashboard
          </button>
        </Card>
      </div>
    );
  }

  const toggleExpand = (code: string) => {
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(code)) next.delete(code);
      else next.add(code);
      return next;
    });
  };

  const handleBulk = async (code: string, action: "approve" | "reject") => {
    const verb = action === "approve" ? "Approve" : "Reject";
    if (!window.confirm(`${verb} ALL pending rates + rules for ${code}?`)) return;
    setBusyCode(code);
    try {
      const fn =
        action === "approve"
          ? api.approvals.approveJurisdiction
          : api.approvals.rejectJurisdiction;
      const res = await fn(code, batchFilter ? { created_by: batchFilter } : undefined);
      toast(
        `${verb}d ${res.approved_rate_ids.length} rates and ${res.approved_rule_ids.length} rules for ${code}`,
        "success"
      );
      refetch();
    } catch (e) {
      console.error(e);
      toast(`Failed to ${action} ${code}`, "error");
    } finally {
      setBusyCode(null);
    }
  };

  return (
    <div className="p-6 sm:p-10 max-w-7xl mx-auto">
      <PageHeader
        title="Pending Approvals"
        description="Review and approve AI-generated draft rates and rules before they go live."
      />

      <div className="grid grid-cols-1 sm:grid-cols-3 gap-5 mb-6">
        <StatCard
          label="Pending Rates"
          value={data?.total_pending_rates ?? 0}
          accent={data && data.total_pending_rates > 0 ? "warning" : "default"}
        />
        <StatCard
          label="Pending Rules"
          value={data?.total_pending_rules ?? 0}
          accent={data && data.total_pending_rules > 0 ? "warning" : "default"}
        />
        <StatCard
          label="Jurisdictions"
          value={data?.total_jurisdictions ?? 0}
          sub="With drafts awaiting review"
        />
      </div>

      <div className="flex flex-wrap items-center gap-3 mb-5">
        <input
          type="search"
          placeholder="Search by code or name…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="input-field text-sm w-64"
        />
        <select
          value={batchFilter}
          onChange={(e) => setBatchFilter(e.target.value)}
          className="input-field text-sm"
        >
          <option value="">All batches</option>
          {allTags.map((t) => (
            <option key={t} value={t}>
              {t}
            </option>
          ))}
        </select>
        {(search || batchFilter) && (
          <button
            onClick={() => {
              setSearch("");
              setBatchFilter("");
            }}
            className="text-sm text-dim hover:text-text"
          >
            Clear filters
          </button>
        )}
        <div className="ml-auto text-sm text-dim">
          Showing {filtered.length} of {rows.length} jurisdictions
        </div>
      </div>

      {loading && !data && (
        <Card className="p-8 text-center text-muted">Loading pending approvals…</Card>
      )}

      {error && (
        <Card className="p-8 text-center">
          <p className="text-danger mb-3">Failed to load: {error}</p>
          <button onClick={refetch} className="btn-primary">
            Retry
          </button>
        </Card>
      )}

      {!loading && !error && filtered.length === 0 && (
        <EmptyState
          icon={CheckCheck}
          title="Nothing to review"
          description={
            rows.length === 0
              ? "No draft rates or rules currently pending."
              : "No jurisdictions match the current filter."
          }
        />
      )}

      <div className="space-y-3">
        {filtered.map((row) => (
          <JurisdictionCard
            key={row.jurisdiction_code}
            row={row}
            expanded={expanded.has(row.jurisdiction_code)}
            onToggle={() => toggleExpand(row.jurisdiction_code)}
            onApproveAll={() => handleBulk(row.jurisdiction_code, "approve")}
            onRejectAll={() => handleBulk(row.jurisdiction_code, "reject")}
            busy={busyCode === row.jurisdiction_code}
            onRefresh={refetch}
            batchFilter={batchFilter}
          />
        ))}
      </div>
    </div>
  );
}

function JurisdictionCard({
  row,
  expanded,
  onToggle,
  onApproveAll,
  onRejectAll,
  busy,
  onRefresh,
  batchFilter,
}: {
  row: PendingSummaryRow;
  expanded: boolean;
  onToggle: () => void;
  onApproveAll: () => void;
  onRejectAll: () => void;
  busy: boolean;
  onRefresh: () => void;
  batchFilter: string;
}) {
  return (
    <Card>
      <div className="p-4 flex flex-wrap items-center gap-3">
        <button
          onClick={onToggle}
          className="flex items-center gap-2 text-sm font-semibold text-text hover:text-accent transition-colors cursor-pointer"
          aria-expanded={expanded}
        >
          {expanded ? (
            <ChevronDown className="w-4 h-4" />
          ) : (
            <ChevronRight className="w-4 h-4" />
          )}
          <span className="font-mono">{row.jurisdiction_code}</span>
          <span className="text-muted font-normal">— {row.jurisdiction_name}</span>
          <Badge value={row.jurisdiction_type} />
        </button>
        <div className="flex items-center gap-3 text-sm text-dim">
          <span>
            <strong className="text-text">{row.pending_rates}</strong> rates
          </span>
          <span>
            <strong className="text-text">{row.pending_rules}</strong> rules
          </span>
          {row.created_by_tags.length > 0 && (
            <span className="text-xs text-dim">
              from {row.created_by_tags.join(", ")}
            </span>
          )}
        </div>
        <div className="ml-auto flex items-center gap-2">
          <button
            onClick={onApproveAll}
            disabled={busy}
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-md bg-success/10 text-success border border-success/25 hover:bg-success/20 cursor-pointer transition-colors disabled:opacity-50"
          >
            <CheckCircle2 className="w-3.5 h-3.5" />
            Approve all
          </button>
          <button
            onClick={onRejectAll}
            disabled={busy}
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-md bg-danger/10 text-danger border border-danger/25 hover:bg-danger/20 cursor-pointer transition-colors disabled:opacity-50"
          >
            <XCircle className="w-3.5 h-3.5" />
            Reject all
          </button>
        </div>
      </div>

      {expanded && (
        <JurisdictionCardBody
          code={row.jurisdiction_code}
          onRefresh={onRefresh}
          batchFilter={batchFilter}
        />
      )}
    </Card>
  );
}

function JurisdictionCardBody({
  code,
  onRefresh,
  batchFilter,
}: {
  code: string;
  onRefresh: () => void;
  batchFilter: string;
}) {
  const { toast } = useToast();
  const [busyId, setBusyId] = useState<string | null>(null);

  const { data: rates, loading: ratesLoading, refetch: refetchRates } = useApi(
    () =>
      api.rates.list({
        jurisdiction_code: code,
        status: "draft",
        limit: "500",
      }),
    [code]
  );
  const { data: rules, loading: rulesLoading, refetch: refetchRules } = useApi(
    () =>
      api.rules.list({
        jurisdiction_code: code,
        status: "draft",
        limit: "500",
      }),
    [code]
  );

  const filteredRates = (rates || []).filter(
    (r) => !batchFilter || r.created_by === batchFilter
  );
  const filteredRules = (rules || []).filter(
    (r) => !batchFilter || r.created_by === batchFilter
  );

  const handleItem = async (
    kind: "rate" | "rule",
    id: number,
    action: "approve" | "reject"
  ) => {
    setBusyId(`${kind}-${id}`);
    try {
      const fn =
        kind === "rate"
          ? action === "approve"
            ? api.rates.approve
            : api.rates.reject
          : action === "approve"
            ? api.rules.approve
            : api.rules.reject;
      await fn(id);
      toast(`${kind} #${id} ${action}d`, "success");
      if (kind === "rate") refetchRates();
      else refetchRules();
      onRefresh();
    } catch (e) {
      console.error(e);
      toast(`Failed to ${action} ${kind} #${id}`, "error");
    } finally {
      setBusyId(null);
    }
  };

  if (ratesLoading || rulesLoading) {
    return <div className="border-t border-border p-4 text-sm text-muted">Loading…</div>;
  }

  return (
    <div className="border-t border-border divide-y divide-border">
      {filteredRates.length === 0 && filteredRules.length === 0 ? (
        <div className="p-4 text-sm text-muted text-center">
          No draft items (may have been approved elsewhere — refresh to sync).
        </div>
      ) : null}

      {filteredRates.length > 0 && (
        <div className="p-4">
          <div className="text-xs font-semibold uppercase tracking-widest text-dim mb-3">
            Rates ({filteredRates.length})
          </div>
          <div className="space-y-2">
            {filteredRates.map((r) => (
              <DraftRateRow
                key={r.id}
                rate={r}
                busy={busyId === `rate-${r.id}`}
                onApprove={() => handleItem("rate", r.id, "approve")}
                onReject={() => handleItem("rate", r.id, "reject")}
              />
            ))}
          </div>
        </div>
      )}

      {filteredRules.length > 0 && (
        <div className="p-4">
          <div className="text-xs font-semibold uppercase tracking-widest text-dim mb-3">
            Rules ({filteredRules.length})
          </div>
          <div className="space-y-2">
            {filteredRules.map((r) => (
              <DraftRuleRow
                key={r.id}
                rule={r}
                busy={busyId === `rule-${r.id}`}
                onApprove={() => handleItem("rule", r.id, "approve")}
                onReject={() => handleItem("rule", r.id, "reject")}
              />
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function DraftRateRow({
  rate,
  busy,
  onApprove,
  onReject,
}: {
  rate: TaxRate;
  busy: boolean;
  onApprove: () => void;
  onReject: () => void;
}) {
  const [showDetail, setShowDetail] = useState(false);
  return (
    <div className="bg-surface rounded-md border border-border">
      <div className="p-3 flex flex-wrap items-center gap-3">
        <span className="font-mono text-xs text-dim">#{rate.id}</span>
        <span className="text-sm font-medium text-text">{rate.tax_category_code}</span>
        <Badge value={rate.rate_type} />
        <span className="font-mono font-semibold text-sm text-text">
          {rate.rate_type === "percentage" && rate.rate_value != null
            ? `${(rate.rate_value * 100).toFixed(3)}%`
            : rate.rate_type === "flat" && rate.rate_value != null
              ? `${rate.currency_code || ""} ${rate.rate_value}`
              : "Tiered"}
        </span>
        <span className="text-xs text-dim">
          eff {formatDate(rate.effective_start)}
          {rate.effective_end && ` → ${formatDate(rate.effective_end)}`}
        </span>
        <button
          onClick={() => setShowDetail((s) => !s)}
          className="text-xs text-dim hover:text-accent"
        >
          {showDetail ? "Hide" : "Details"}
        </button>
        <div className="ml-auto flex items-center gap-1.5">
          <button
            onClick={onApprove}
            disabled={busy}
            className="flex items-center gap-1 px-2 py-1 text-xs font-medium rounded bg-success/10 text-success border border-success/25 hover:bg-success/20 cursor-pointer disabled:opacity-50"
            title="Approve this rate"
          >
            <CheckCircle2 className="w-3.5 h-3.5" />
          </button>
          <button
            onClick={onReject}
            disabled={busy}
            className="flex items-center gap-1 px-2 py-1 text-xs font-medium rounded bg-danger/10 text-danger border border-danger/25 hover:bg-danger/20 cursor-pointer disabled:opacity-50"
            title="Reject this rate"
          >
            <XCircle className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>

      {showDetail && (
        <div className="border-t border-border p-3 text-xs space-y-2">
          {rate.authority_name && (
            <div>
              <span className="text-dim">Authority: </span>
              <span className="text-text">{rate.authority_name}</span>
            </div>
          )}
          {rate.legal_reference && (
            <div>
              <span className="text-dim">Legal: </span>
              <span className="text-text">{rate.legal_reference}</span>
            </div>
          )}
          {rate.source_url && (
            <div>
              <span className="text-dim">Source: </span>
              <a
                href={rate.source_url}
                target="_blank"
                rel="noopener noreferrer"
                className="text-accent hover:underline break-all"
              >
                {rate.source_url}
              </a>
            </div>
          )}
          {rate.created_by && (
            <div>
              <span className="text-dim">Batch: </span>
              <span className="font-mono text-muted">{rate.created_by}</span>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function DraftRuleRow({
  rule,
  busy,
  onApprove,
  onReject,
}: {
  rule: TaxRule;
  busy: boolean;
  onApprove: () => void;
  onReject: () => void;
}) {
  const [showDetail, setShowDetail] = useState(false);
  return (
    <div className="bg-surface rounded-md border border-border">
      <div className="p-3 flex flex-wrap items-center gap-3">
        <span className="font-mono text-xs text-dim">#{rule.id}</span>
        <Badge value={rule.rule_type} />
        <span className="text-sm text-text flex-1 min-w-0 truncate" title={rule.name}>
          {rule.name}
        </span>
        {rule.tax_rate_id != null && (
          <span className="text-xs text-dim font-mono">→ rate #{rule.tax_rate_id}</span>
        )}
        <button
          onClick={() => setShowDetail((s) => !s)}
          className="text-xs text-dim hover:text-accent"
        >
          {showDetail ? "Hide" : "Details"}
        </button>
        <div className="flex items-center gap-1.5">
          <button
            onClick={onApprove}
            disabled={busy}
            className="flex items-center gap-1 px-2 py-1 text-xs font-medium rounded bg-success/10 text-success border border-success/25 hover:bg-success/20 cursor-pointer disabled:opacity-50"
            title="Approve this rule"
          >
            <CheckCircle2 className="w-3.5 h-3.5" />
          </button>
          <button
            onClick={onReject}
            disabled={busy}
            className="flex items-center gap-1 px-2 py-1 text-xs font-medium rounded bg-danger/10 text-danger border border-danger/25 hover:bg-danger/20 cursor-pointer disabled:opacity-50"
            title="Reject this rule"
          >
            <XCircle className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>

      {showDetail && (
        <div className="border-t border-border p-3 text-xs space-y-2">
          {rule.description && (
            <div className="text-muted italic">{rule.description}</div>
          )}
          {rule.conditions && Object.keys(rule.conditions).length > 0 && (
            <div>
              <span className="text-dim">Conditions: </span>
              <pre className="inline font-mono text-muted">
                {JSON.stringify(rule.conditions)}
              </pre>
            </div>
          )}
          {rule.action && Object.keys(rule.action).length > 0 && (
            <div>
              <span className="text-dim">Action: </span>
              <pre className="inline font-mono text-muted">
                {JSON.stringify(rule.action)}
              </pre>
            </div>
          )}
          {rule.legal_reference && (
            <div>
              <span className="text-dim">Legal: </span>
              <span className="text-text">{rule.legal_reference}</span>
            </div>
          )}
          {rule.created_by && (
            <div>
              <span className="text-dim">Batch: </span>
              <span className="font-mono text-muted">{rule.created_by}</span>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
