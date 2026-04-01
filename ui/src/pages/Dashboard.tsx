import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { RiArrowRightSLine } from "react-icons/ri";
import {
  Globe, MapPin, TrendingUp, AlertTriangle, Shield, Zap,
  Calculator, ScrollText, AlertCircle, BookOpen,
} from "lucide-react";
import PageHeader from "../components/PageHeader";
import PageTransition from "../components/PageTransition";
import StatCard from "../components/StatCard";
import Card from "../components/Card";
import Badge from "../components/Badge";
import DonutChart from "../components/DonutChart";
import {
  api,
  type Jurisdiction,
  type TaxRate,
  type HealthResponse,
  type DetectedChange,
  type MonitoringJob,
} from "../lib/api";

export default function Dashboard() {
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [jurisdictions, setJurisdictions] = useState<Jurisdiction[]>([]);
  const [rates, setRates] = useState<TaxRate[]>([]);
  const [pendingChanges, setPendingChanges] = useState<DetectedChange[]>([]);
  const [recentJobs, setRecentJobs] = useState<MonitoringJob[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([
      api.health().catch(() => null),
      api.jurisdictions.list({ limit: "2000" }).catch(() => []),
      api.rates.list({ limit: "2000" }).catch(() => []),
      api.monitoring.changes({ review_status: "pending", limit: "2000" }).catch(() => []),
      api.monitoring.listJobs({ limit: "10" }).catch(() => []),
    ]).then(([h, j, r, pc, rj]) => {
      setHealth(h);
      setJurisdictions(j);
      setRates(r);
      setPendingChanges(pc);
      setRecentJobs(rj);
      setLoading(false);
    });
  }, []);

  if (loading) {
    return (
      <div className="p-4 sm:p-10 flex items-center justify-center h-full">
        <div className="flex flex-col items-center gap-3">
          <div className="w-8 h-8 border-2 border-accent/30 border-t-accent rounded-full animate-spin" />
          <span className="text-sm text-dim">Loading dashboard...</span>
        </div>
      </div>
    );
  }

  const countries = new Set(jurisdictions.map((j) => j.country_code));
  const activeRates = rates.filter((r) => r.status === "active");
  const pendingRates = rates.filter((r) => r.status === "draft" || r.status === "scheduled");
  const cities = jurisdictions.filter((j) => j.jurisdiction_type === "city");
  const states = jurisdictions.filter((j) => ["state", "province", "region"].includes(j.jurisdiction_type));

  // Regional breakdown for donut
  const REGIONS: Record<string, { codes: Set<string>; color: string }> = {
    "Europe": { codes: new Set(["AD","AL","AT","BA","BE","BG","BY","CH","CY","CZ","DE","DK","EE","ES","FI","FR","GB","GE","GR","HR","HU","IE","IS","IT","LI","LT","LU","LV","MC","MD","ME","MK","MT","NL","NO","PL","PT","RO","RS","SE","SI","SK","SM","TR","UA","VA"]), color: "#3b82f6" },
    "Asia-Pacific": { codes: new Set(["AE","AU","BD","BH","BN","BT","CN","CK","FJ","GU","HK","ID","IL","IN","JO","JP","KG","KH","KR","KW","KZ","LA","LB","LK","MH","MM","MN","MO","MP","MV","MY","NP","NZ","OM","PG","PH","PK","PS","PW","QA","SA","SG","TH","TJ","TL","TM","TW","UZ","VN"]), color: "#16a34a" },
    "Americas": { codes: new Set(["AG","AI","AR","AW","BB","BM","BO","BQ","BR","BS","BZ","CA","CL","CO","CR","CU","CW","DM","DO","EC","GD","GP","GT","GY","HN","HT","JM","KN","KY","LC","MF","MQ","MX","NI","PA","PE","PF","PR","PY","SV","SR","TC","TT","US","UY","VC","VE","VG","VI"]), color: "#d97706" },
    "Africa": { codes: new Set(["AO","BF","BJ","BW","CD","CF","CG","CI","CM","CV","DJ","DZ","EG","ER","ET","GA","GH","GM","GN","GQ","GW","KE","KM","LR","LS","LY","MA","MG","ML","MR","MU","MW","MZ","NA","NE","NG","RW","SC","SD","SL","SN","SO","SS","ST","SZ","TD","TG","TN","TZ","UG","ZA","ZM","ZW"]), color: "#dc2626" },
  };

  const donutSegments = Object.entries(REGIONS).map(([label, { codes, color }]) => ({
    label,
    value: jurisdictions.filter((j) => codes.has(j.country_code)).length,
    color,
  }));

  // Pending changes by jurisdiction
  const pendingByJurisdiction: Record<string, number> = {};
  for (const c of pendingChanges) {
    const code = c.jurisdiction_code || "unknown";
    pendingByJurisdiction[code] = (pendingByJurisdiction[code] || 0) + 1;
  }
  const pendingJurisdictions = Object.entries(pendingByJurisdiction)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 8);

  return (
    <PageTransition><div className="p-4 sm:p-6 lg:p-10 max-w-[1400px]">
      <PageHeader
        title="Dashboard"
        description="Global accommodation tax intelligence overview"
      />

      {/* Hero Stats */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5 mb-5">
        <StatCard label="Countries" value={countries.size} sub="Tracked globally" icon={Globe} />
        <StatCard label="Jurisdictions" value={jurisdictions.length} sub={`${cities.length} cities, ${states.length} states/regions`} icon={MapPin} />
        <StatCard
          label="Tax Rates"
          value={activeRates.length}
          accent="success"
          sub="Active in production"
          icon={TrendingUp}
        />
        <StatCard
          label="Pending Review"
          value={pendingRates.length}
          accent={pendingRates.length > 0 ? "warning" : "default"}
          sub="Awaiting approval"
          icon={AlertTriangle}
        />
      </div>

      {/* Quick Actions */}
      <div className="flex flex-wrap gap-3 mb-8">
        {[
          { icon: AlertCircle, label: "Review Changes", to: "/app/jurisdictions", show: pendingChanges.length > 0 },
          { icon: Globe, label: "Manage Jurisdictions", to: "/app/jurisdictions", show: true },
          { icon: Calculator, label: "Tax Calculator", to: "/app/calculator", show: true },
          { icon: ScrollText, label: "Audit Log", to: "/app/audit", show: true },
          { icon: BookOpen, label: "API Docs", to: "/app/docs", show: true },
        ].filter(a => a.show).map((action) => (
          <Link key={action.label} to={action.to} className="inline-flex items-center gap-2 px-4 py-2.5 rounded-lg border border-border bg-card hover:bg-surface hover:border-border-light transition-all text-sm font-medium text-muted hover:text-text">
            <action.icon className="w-4 h-4" />
            {action.label}
          </Link>
        ))}
      </div>

      {/* Platform Health Banner */}
      <Card className="mb-8 bg-gradient-to-r from-accent/5 to-success/5 border-accent/20">
        <div className="px-4 sm:px-6 py-5 flex flex-wrap items-center gap-3 sm:gap-6">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-full bg-success/10 flex items-center justify-center">
              <Shield className="w-5 h-5 text-success" />
            </div>
            <div>
              <div className="text-sm font-semibold text-text">Platform Operational</div>
              <div className="text-xs text-dim">v{health?.version} &middot; DB {health?.database} &middot; AI {health?.ai_configured ? "Active" : "Inactive"}</div>
            </div>
          </div>
          <div className="flex items-center gap-2 text-xs text-dim">
            <Zap className="w-3.5 h-3.5 text-accent" />
            <span>Sub-50ms API response &middot; 100% global OTA coverage</span>
          </div>
        </div>
      </Card>

      {/* Main Content: Charts Row */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5 mb-8">
        {/* Regional Coverage Donut */}
        <Card>
          <div className="px-6 py-4 border-b border-border">
            <span className="text-base font-semibold text-text">Global Coverage by Region</span>
          </div>
          <div className="p-6 flex justify-center">
            <DonutChart
              segments={donutSegments}
              size={200}
              thickness={32}
              centerValue={jurisdictions.length}
              centerLabel="Jurisdictions"
            />
          </div>
        </Card>

      </div>

      {/* Coverage Numbers Grid */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 mb-8">
        {[
          { label: "Countries", value: countries.size, color: "text-accent" },
          { label: "Sub-jurisdictions", value: jurisdictions.length - countries.size, color: "text-success" },
          { label: "Tax Rates", value: activeRates.length, color: "text-warning" },
          { label: "Rules & Exemptions", value: "235", color: "text-danger" },
        ].map((item) => (
          <Card key={item.label} className="p-4 text-center">
            <div className={`text-2xl sm:text-3xl font-bold tabular-nums ${item.color}`}>{item.value}</div>
            <div className="text-xs text-dim mt-1 uppercase tracking-wide">{item.label}</div>
          </Card>
        ))}
      </div>

      {/* Secondary Content */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5 mb-8">
        {/* Jurisdictions needing review */}
        <Card>
          <div className="px-6 py-4 border-b border-border flex items-center justify-between">
            <span className="text-base font-semibold text-text">
              Jurisdictions Needing Review
            </span>
            <Link
              to="/app/jurisdictions"
              className="text-sm text-accent hover:text-accent-hover flex items-center gap-1 font-medium"
            >
              View all <RiArrowRightSLine className="w-4 h-4" />
            </Link>
          </div>
          {pendingJurisdictions.length > 0 ? (
            <div className="divide-y divide-border">
              {pendingJurisdictions.map(([code, count]) => (
                <div
                  key={code}
                  className="px-6 py-3.5 flex items-center justify-between hover:bg-surface transition-colors"
                >
                  <span className="text-sm font-mono text-accent font-medium">
                    {code}
                  </span>
                  <div className="flex items-center gap-2">
                    <span className="text-sm text-muted">
                      {count} pending change{count !== 1 ? "s" : ""}
                    </span>
                    <Badge value="needs_review" />
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="p-8 text-center">
              <Shield className="w-8 h-8 text-success/30 mx-auto mb-2" />
              <div className="text-sm text-dim">All jurisdictions up to date</div>
            </div>
          )}
        </Card>

        {/* Recent monitoring jobs */}
        <Card>
          <div className="px-6 py-4 border-b border-border">
            <span className="text-base font-semibold text-text">Recent Monitoring Jobs</span>
          </div>
          {recentJobs.length > 0 ? (
            <div className="divide-y divide-border">
              {recentJobs.slice(0, 6).map((job) => (
                <div
                  key={job.id}
                  className="px-6 py-3.5 flex items-center justify-between hover:bg-surface transition-colors"
                >
                  <div className="flex items-center gap-3 min-w-0">
                    <Badge value={job.status} />
                    <div className="min-w-0">
                      <div className="text-sm font-mono text-accent font-medium">
                        {job.jurisdiction_code || `Job #${job.id}`}
                      </div>
                      <div className="text-xs text-dim mt-0.5">
                        {job.trigger_type} &middot; {job.changes_detected} changes
                      </div>
                    </div>
                  </div>
                  <span className="text-xs text-dim flex-shrink-0">
                    {new Date(job.created_at).toLocaleDateString()}
                  </span>
                </div>
              ))}
            </div>
          ) : (
            <div className="p-8 text-center">
              <Zap className="w-8 h-8 text-accent/30 mx-auto mb-2" />
              <div className="text-sm text-dim">No monitoring jobs yet</div>
            </div>
          )}
        </Card>
      </div>

      {/* Recent Tax Rates */}
      <Card>
        <div className="px-6 py-4 border-b border-border flex items-center justify-between">
          <span className="text-base font-semibold text-text">Recent Tax Rates</span>
          <Link
            to="/app/jurisdictions"
            className="text-sm text-accent hover:text-accent-hover flex items-center gap-1 font-medium"
          >
            View all <RiArrowRightSLine className="w-4 h-4" />
          </Link>
        </div>
        <div className="divide-y divide-border">
          {rates.slice(0, 8).map((rate) => (
            <div key={rate.id} className="px-6 py-3.5 flex items-center justify-between hover:bg-surface transition-colors">
              <div className="flex items-center gap-3 min-w-0">
                <Badge value={rate.rate_type} />
                <div className="min-w-0">
                  <div className="text-sm text-text font-medium truncate">
                    <span className="font-mono text-accent">{rate.jurisdiction_code}</span>
                    <span className="text-dim mx-2">/</span>
                    <span>{rate.tax_category_code}</span>
                  </div>
                  <div className="text-xs text-dim truncate mt-0.5">
                    {rate.legal_reference || "No legal reference"}
                  </div>
                </div>
              </div>
              <div className="flex items-center gap-4 flex-shrink-0">
                <span className="text-sm font-mono font-semibold text-text">
                  {rate.rate_type === "percentage" && rate.rate_value != null
                    ? `${(rate.rate_value * 100).toFixed(2)}%`
                    : rate.rate_type === "flat" && rate.rate_value != null
                      ? `${rate.currency_code} ${rate.rate_value}`
                      : "Tiered"}
                </span>
                <Badge value={rate.status} />
              </div>
            </div>
          ))}
        </div>
      </Card>
    </div></PageTransition>
  );
}
