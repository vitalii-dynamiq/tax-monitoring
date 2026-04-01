import { useState, useMemo } from "react";
import Card from "../../components/Card";
import Badge from "../../components/Badge";
import DataTable, { type Column } from "../../components/DataTable";
import {
  api,
  type Jurisdiction,
  type TaxRate,
  type MonitoredSource,
  type RateLookupResponse,
  type TaxCalculationResponse,
} from "../../lib/api";
import { useToast } from "../../hooks/useToast";
import { formatDate, formatDateTime, formatCurrency, formatPercent, cn } from "../../lib/utils";
import {
  ChevronRight,
  Globe,
  Map as MapIcon,
  Building2,
  MapPin,
  Star,
} from "lucide-react";

// ─── Constants ──────────────────────────────────────────────

const TYPE_ICONS: Record<string, typeof Globe> = {
  country: Globe,
  state: MapIcon,
  province: MapIcon,
  region: MapIcon,
  city: Building2,
  district: MapPin,
  special_zone: Star,
};

// ─── Overview Tab ───────────────────────────────────────────

export default function OverviewTab({
  current,
  children,
  childrenLoading,
  onNavigate,
  ancestors,
  lookupRates,
  lookupLoading,
  sampleCalc,
  sampleCalcLoading,
  isSubJurisdiction,
  sources,
  sourcesLoading,
}: {
  current: Jurisdiction;
  children: Jurisdiction[];
  childrenLoading: boolean;
  onNavigate: (code: string) => void;
  ancestors: Jurisdiction[];
  lookupRates: RateLookupResponse | null;
  lookupLoading: boolean;
  sampleCalc: TaxCalculationResponse | null;
  sampleCalcLoading: boolean;
  isSubJurisdiction: boolean;
  sources: MonitoredSource[];
  sourcesLoading: boolean;
}) {
  return (
    <div className="space-y-6">
      <JurisdictionHeader jurisdiction={current} />

      <RegulatorySourcesSection
        sources={sources}
        loading={sourcesLoading}
        jurisdictionCode={current.code}
      />

      {isSubJurisdiction && (
        <CombinedTaxOverview
          current={current}
          ancestors={ancestors}
          lookupRates={lookupRates}
          lookupLoading={lookupLoading}
          sampleCalc={sampleCalc}
          sampleCalcLoading={sampleCalcLoading}
        />
      )}

      <ChildrenSection
        children={children}
        loading={childrenLoading}
        onNavigate={onNavigate}
      />
    </div>
  );
}

// ─── Jurisdiction Header Card ───────────────────────────────

function JurisdictionHeader({ jurisdiction }: { jurisdiction: Jurisdiction }) {
  return (
    <Card className="p-6">
      <div className="flex items-start gap-4">
        {(() => {
          const Icon = TYPE_ICONS[jurisdiction.jurisdiction_type] || MapPin;
          return (
            <div className="w-12 h-12 rounded-lg bg-accent/10 flex items-center justify-center flex-shrink-0">
              <Icon className="w-6 h-6 text-accent" />
            </div>
          );
        })()}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-3 flex-wrap">
            <h2 className="text-xl font-semibold text-text">{jurisdiction.name}</h2>
            {jurisdiction.local_name && (
              <span className="text-sm text-dim">{jurisdiction.local_name}</span>
            )}
          </div>
          <div className="flex items-center gap-2 mt-2 flex-wrap">
            <Badge value={jurisdiction.jurisdiction_type} />
            <Badge value={jurisdiction.status} />
            <span className="font-mono text-xs text-accent bg-accent/10 px-2 py-0.5 rounded">
              {jurisdiction.code}
            </span>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-2 sm:grid-cols-4 gap-6 mt-6 pt-6 border-t border-border">
        <PropField label="Country Code" value={jurisdiction.country_code} mono />
        <PropField label="Currency" value={jurisdiction.currency_code} mono />
        <PropField label="Timezone" value={jurisdiction.timezone} />
        <PropField label="Subdivision" value={jurisdiction.subdivision_code} mono />
        {jurisdiction.path && (
          <PropField label="Path" value={jurisdiction.path} mono />
        )}
        <PropField label="Created" value={formatDate(jurisdiction.created_at)} />
        <PropField label="Updated" value={formatDate(jurisdiction.updated_at)} />
      </div>
    </Card>
  );
}

function PropField({
  label,
  value,
  mono,
}: {
  label: string;
  value: string | null | undefined;
  mono?: boolean;
}) {
  return (
    <div>
      <div className="text-xs font-semibold uppercase tracking-widest text-dim mb-1">
        {label}
      </div>
      <div className={cn("text-sm text-text", mono && "font-mono", !value && "text-dim")}>
        {value || "\u2014"}
      </div>
    </div>
  );
}

// ─── Regulatory Sources Section ─────────────────────────────

const SOURCE_COLUMNS: Column<MonitoredSource>[] = [
  {
    key: "type",
    header: "Type",
    render: (r) => <Badge value={r.source_type} />,
    className: "w-36",
  },
  {
    key: "url",
    header: "URL",
    render: (r) => (
      <a
        href={r.url}
        target="_blank"
        rel="noopener noreferrer"
        className="text-accent hover:underline text-sm truncate block max-w-[400px]"
      >
        {r.url}
      </a>
    ),
  },
  {
    key: "frequency",
    header: "Freq.",
    render: (r) => <span className="text-muted font-mono text-xs">{r.check_frequency_days}d</span>,
    className: "w-16",
  },
  {
    key: "last_checked",
    header: "Last Checked",
    render: (r) => (
      <span className="text-dim text-sm">{formatDateTime(r.last_checked_at)}</span>
    ),
  },
  {
    key: "status",
    header: "Status",
    render: (r) => <Badge value={r.status} />,
    className: "w-24",
  },
];

function RegulatorySourcesSection({
  sources,
  loading,
  jurisdictionCode,
  onSourceAdded,
}: {
  sources: MonitoredSource[];
  loading: boolean;
  jurisdictionCode: string;
  onSourceAdded?: () => void;
}) {
  const { toast } = useToast();
  const [showAdd, setShowAdd] = useState(false);
  const [domain, setDomain] = useState("");
  const [sourceType, setSourceType] = useState("government_website");
  const [saving, setSaving] = useState(false);

  const handleAdd = async () => {
    if (!domain.trim()) return;
    setSaving(true);
    try {
      await api.monitoring.createSource({
        jurisdiction_code: jurisdictionCode,
        url: domain.trim().replace(/^https?:\/\//, "").replace(/\/.*$/, ""),
        source_type: sourceType,
      });
      toast("Source added successfully", "success");
      setDomain("");
      setShowAdd(false);
      onSourceAdded?.();
    } catch (e) {
      console.error("Failed to add source:", e);
      toast("Failed to add source", "error");
    } finally {
      setSaving(false);
    }
  };

  return (
    <Card>
      <div className="px-6 py-4 border-b border-border flex items-center justify-between">
        <h3 className="text-sm font-semibold uppercase tracking-widest text-dim">
          Regulatory Sources{!loading && ` (${sources.length})`}
        </h3>
        <button
          onClick={() => setShowAdd(!showAdd)}
          className="text-xs text-accent hover:underline cursor-pointer font-medium"
        >
          {showAdd ? "Cancel" : "+ Add Source"}
        </button>
      </div>
      {showAdd && (
        <div className="px-6 py-4 border-b border-border bg-surface/50 flex items-end gap-3">
          <div className="flex-1">
            <label className="block text-xs text-dim mb-1">Domain</label>
            <input
              type="text"
              value={domain}
              onChange={(e) => setDomain(e.target.value)}
              placeholder="e.g. nyc.gov"
              className="input-field w-full text-sm"
            />
          </div>
          <div className="w-48">
            <label className="block text-xs text-dim mb-1">Type</label>
            <select
              value={sourceType}
              onChange={(e) => setSourceType(e.target.value)}
              className="input-field w-full text-sm"
            >
              <option value="government_website">Government Website</option>
              <option value="tax_authority">Tax Authority</option>
              <option value="legal_gazette">Legal Gazette</option>
              <option value="regulatory_body">Regulatory Body</option>
            </select>
          </div>
          <button
            onClick={handleAdd}
            disabled={saving || !domain.trim()}
            className="btn-primary px-4 py-2 text-sm flex-shrink-0"
          >
            {saving ? "Adding..." : "Add"}
          </button>
        </div>
      )}
      <DataTable
        columns={SOURCE_COLUMNS}
        data={sources}
        loading={loading}
        emptyMessage="No regulatory sources configured — click '+ Add Source' to add one"
      />
    </Card>
  );
}

// ─── Children Section ───────────────────────────────────────

function ChildrenSection({
  children,
  loading,
  onNavigate,
}: {
  children: Jurisdiction[];
  loading: boolean;
  onNavigate: (code: string) => void;
}) {
  return (
    <Card>
      <div className="px-6 py-4 border-b border-border">
        <h3 className="text-sm font-semibold uppercase tracking-widest text-dim">
          Sub-Jurisdictions{!loading && ` (${children.length})`}
        </h3>
      </div>

      {loading ? (
        <div className="flex items-center justify-center py-12">
          <div className="w-6 h-6 border-2 border-accent/30 border-t-accent rounded-full animate-spin" />
        </div>
      ) : children.length === 0 ? (
        <div className="px-6 py-10 text-sm text-dim text-center">
          No sub-jurisdictions
        </div>
      ) : (
        <div>
          {children.map((child) => {
            const Icon = TYPE_ICONS[child.jurisdiction_type] || MapPin;
            return (
              <div
                key={child.code}
                onClick={() => onNavigate(child.code)}
                className="flex items-center gap-4 px-6 py-4 border-b border-border last:border-b-0 cursor-pointer hover:bg-surface/60 transition-colors group"
              >
                <div className="w-9 h-9 rounded-lg bg-accent/8 flex items-center justify-center flex-shrink-0 group-hover:bg-accent/12 transition-colors">
                  <Icon className="w-4.5 h-4.5 text-accent/70" />
                </div>
                <div className="flex-1 min-w-0">
                  <div className="font-medium text-sm text-text truncate">
                    {child.name}
                  </div>
                  {child.local_name && (
                    <div className="text-xs text-dim truncate mt-0.5">{child.local_name}</div>
                  )}
                </div>
                <span className="font-mono text-xs text-accent bg-accent/10 px-2 py-0.5 rounded flex-shrink-0">
                  {child.code}
                </span>
                <Badge value={child.jurisdiction_type} />
                <ChevronRight className="w-4 h-4 text-dim group-hover:text-accent transition-colors flex-shrink-0" />
              </div>
            );
          })}
        </div>
      )}
    </Card>
  );
}

// ─── Combined Tax Overview ───────────────────────────────────

function CombinedTaxOverview({
  current,
  ancestors,
  lookupRates,
  lookupLoading,
  sampleCalc,
  sampleCalcLoading,
}: {
  current: Jurisdiction;
  ancestors: Jurisdiction[];
  lookupRates: RateLookupResponse | null;
  lookupLoading: boolean;
  sampleCalc: TaxCalculationResponse | null;
  sampleCalcLoading: boolean;
}) {
  const isLoading = lookupLoading || sampleCalcLoading;

  const jurisdictionNames = useMemo(() => {
    const map: Record<string, { name: string; type: string }> = {};
    for (const a of ancestors) {
      map[a.code] = { name: a.name, type: a.jurisdiction_type };
    }
    map[current.code] = { name: current.name, type: current.jurisdiction_type };
    return map;
  }, [ancestors, current]);

  const orderedCodes = useMemo(
    () => [...ancestors.map((a) => a.code), current.code],
    [ancestors, current]
  );

  const componentGroups = useMemo(() => {
    if (!sampleCalc?.tax_breakdown.components) return [];
    const groups: Record<string, typeof sampleCalc.tax_breakdown.components> = {};
    for (const c of sampleCalc.tax_breakdown.components) {
      const code = c.jurisdiction_code;
      if (!groups[code]) groups[code] = [];
      groups[code].push(c);
    }
    return orderedCodes
      .filter((code) => groups[code])
      .map((code) => ({
        code,
        name: jurisdictionNames[code]?.name || code,
        type: jurisdictionNames[code]?.type || "",
        isLocal: code === current.code,
        components: groups[code],
        subtotal: groups[code].reduce((sum, c) => sum + c.tax_amount, 0),
      }));
  }, [sampleCalc, orderedCodes, current.code, jurisdictionNames]);

  const rateGroups = useMemo(() => {
    if (!lookupRates?.rates || componentGroups.length > 0) return [];
    const groups: Record<string, TaxRate[]> = {};
    for (const rate of lookupRates.rates) {
      const code = rate.jurisdiction_code;
      if (!groups[code]) groups[code] = [];
      groups[code].push(rate);
    }
    return orderedCodes
      .filter((code) => groups[code])
      .map((code) => ({
        code,
        name: jurisdictionNames[code]?.name || code,
        type: jurisdictionNames[code]?.type || "",
        isLocal: code === current.code,
        rates: groups[code],
      }));
  }, [lookupRates, componentGroups.length, orderedCodes, current.code, jurisdictionNames]);

  const currency = sampleCalc?.tax_breakdown.currency || current.currency_code || "USD";

  return (
    <Card>
      <div className="px-6 py-4 border-b border-border flex items-center justify-between">
        <h3 className="text-sm font-semibold uppercase tracking-widest text-dim">
          Combined Tax Overview
        </h3>
        {!isLoading && sampleCalc && (
          <span className="text-lg font-bold font-mono text-accent">
            {formatPercent(sampleCalc.tax_breakdown.effective_rate)}
          </span>
        )}
        {!isLoading && !sampleCalc && lookupRates && (
          <span className="text-lg font-bold font-mono text-accent">
            {formatPercent(lookupRates.combined_percentage_rate)}
          </span>
        )}
      </div>

      {isLoading ? (
        <div className="flex items-center justify-center py-12">
          <div className="w-6 h-6 border-2 border-accent/30 border-t-accent rounded-full animate-spin" />
        </div>
      ) : (
        <div className="p-6 space-y-6">
          {sampleCalc && (
            <>
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                <div className="bg-surface rounded-lg p-4 border border-border">
                  <div className="text-xs font-semibold uppercase tracking-widest text-dim mb-1">
                    Effective Rate
                  </div>
                  <div className="text-xl font-bold font-mono text-accent">
                    {formatPercent(sampleCalc.tax_breakdown.effective_rate)}
                  </div>
                </div>
                <div className="bg-surface rounded-lg p-4 border border-border">
                  <div className="text-xs font-semibold uppercase tracking-widest text-dim mb-1">
                    Total Tax
                  </div>
                  <div className="text-xl font-bold font-mono text-warning">
                    {formatCurrency(sampleCalc.tax_breakdown.total_tax, currency)}
                  </div>
                </div>
                <div className="bg-surface rounded-lg p-4 border border-border">
                  <div className="text-xs font-semibold uppercase tracking-widest text-dim mb-1">
                    Total with Tax
                  </div>
                  <div className="text-xl font-bold font-mono text-success">
                    {formatCurrency(sampleCalc.total_with_tax, currency)}
                  </div>
                </div>
              </div>
              <div className="text-xs text-dim">
                Sample: 3 nights at {formatCurrency(200, currency)}/night (hotel)
              </div>
            </>
          )}

          {componentGroups.length > 0 ? (
            <div className="space-y-4">
              {componentGroups.map((group) => (
                <div key={group.code} className="rounded-lg border border-border overflow-hidden">
                  <div className={cn(
                    "px-4 py-3 flex items-center justify-between",
                    group.isLocal ? "bg-accent/5" : "bg-surface"
                  )}>
                    <div className="flex items-center gap-2">
                      <span className="font-semibold text-sm text-text">{group.name}</span>
                      <Badge value={group.type} />
                    </div>
                    <div className="flex items-center gap-3">
                      <span className={cn(
                        "text-xs font-semibold px-2 py-0.5 rounded-md uppercase",
                        group.isLocal
                          ? "bg-accent/15 text-accent"
                          : "bg-surface text-dim border border-border"
                      )}>
                        {group.isLocal ? "local" : "inherited"}
                      </span>
                      <span className="font-mono text-sm font-semibold text-text">
                        {formatCurrency(group.subtotal, currency)}
                      </span>
                    </div>
                  </div>
                  <div className="divide-y divide-border">
                    {group.components.map((c, i) => (
                      <div key={i} className="px-4 py-3 flex items-center justify-between">
                        <div className="flex items-center gap-3">
                          <Badge value={c.rate_type} />
                          <span className="text-sm text-text">{c.name}</span>
                        </div>
                        <div className="text-right">
                          <span className="font-mono text-sm font-medium text-text">
                            {formatCurrency(c.tax_amount, currency)}
                          </span>
                          {c.rate != null && (
                            <span className="text-xs text-dim font-mono ml-2">
                              {c.rate_type === "percentage"
                                ? formatPercent(c.rate)
                                : `${formatCurrency(c.rate, currency)} flat`}
                            </span>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          ) : rateGroups.length > 0 ? (
            <div className="space-y-4">
              {rateGroups.map((group) => (
                <div key={group.code} className="rounded-lg border border-border overflow-hidden">
                  <div className={cn(
                    "px-4 py-3 flex items-center justify-between",
                    group.isLocal ? "bg-accent/5" : "bg-surface"
                  )}>
                    <div className="flex items-center gap-2">
                      <span className="font-semibold text-sm text-text">{group.name}</span>
                      <Badge value={group.type} />
                    </div>
                    <span className={cn(
                      "text-xs font-semibold px-2 py-0.5 rounded-md uppercase",
                      group.isLocal
                        ? "bg-accent/15 text-accent"
                        : "bg-surface text-dim border border-border"
                    )}>
                      {group.isLocal ? "local" : "inherited"}
                    </span>
                  </div>
                  <div className="divide-y divide-border">
                    {group.rates.map((r, i) => (
                      <div key={i} className="px-4 py-3 flex items-center justify-between">
                        <div className="flex items-center gap-3">
                          <Badge value={r.rate_type} />
                          <span className="font-mono text-xs text-dim">{r.tax_category_code}</span>
                        </div>
                        <span className="font-mono text-sm text-text">
                          {r.rate_type === "percentage" && r.rate_value != null
                            ? formatPercent(r.rate_value)
                            : r.rate_type === "flat" && r.rate_value != null
                              ? `${r.currency_code} ${r.rate_value}`
                              : "Tiered"}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="text-sm text-dim text-center py-6">
              No combined tax data available
            </div>
          )}

          {sampleCalc && sampleCalc.rules_applied.length > 0 && (
            <div>
              <div className="text-xs font-semibold uppercase tracking-widest text-dim mb-2">
                Rules Evaluated
              </div>
              <div className="rounded-lg border border-border divide-y divide-border">
                {sampleCalc.rules_applied.map((r, i) => (
                  <div key={i} className="px-4 py-2.5 flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <Badge value={r.rule_type} />
                      <span className="text-sm text-text">{r.name}</span>
                    </div>
                    <span className={cn(
                      "text-xs font-semibold px-2 py-0.5 rounded-md uppercase",
                      r.result === "applied"
                        ? "bg-success/15 text-success"
                        : r.result === "exempted"
                          ? "bg-warning/15 text-warning"
                          : "bg-surface text-dim"
                    )}>
                      {r.result}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </Card>
  );
}
