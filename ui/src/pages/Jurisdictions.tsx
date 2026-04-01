import { useState, useMemo, useEffect } from "react";
import PageHeader from "../components/PageHeader";
import PageTransition from "../components/PageTransition";
import Card from "../components/Card";
import StatCard from "../components/StatCard";
import CreateJurisdictionModal from "../components/CreateJurisdictionModal";
import {
  api,
  type Jurisdiction,
  type RateLookupResponse,
  type TaxCalculationResponse,
  type MonitoredSource,
} from "../lib/api";
import { useApi } from "../hooks/useApi";
import {
  ChevronRight,
  Globe,
  Map as MapIcon,
  Building2,
  MapPin,
  Star,
  Home,
  ArrowLeft,
} from "lucide-react";

import OverviewTab from "./jurisdictions/OverviewTab";
import RatesTab from "./jurisdictions/RatesTab";
import RulesTab from "./jurisdictions/RulesTab";
import ChangesTab from "./jurisdictions/ChangesTab";
import MonitoringTab from "./jurisdictions/MonitoringTab";
import DiscoveryTab from "./jurisdictions/DiscoveryTab";

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

type JurisdictionTab = "overview" | "rates" | "rules" | "changes" | "monitoring" | "discovery";

const TABS_DEFAULT: { key: JurisdictionTab; label: string }[] = [
  { key: "overview", label: "Overview" },
  { key: "rates", label: "Rates" },
  { key: "rules", label: "Rules" },
  { key: "changes", label: "Changes" },
  { key: "monitoring", label: "Monitoring" },
];

const TABS_COUNTRY: { key: JurisdictionTab; label: string }[] = [
  ...TABS_DEFAULT,
  { key: "discovery", label: "Discovery" },
];

// ─── Spinner ────────────────────────────────────────────────

function Spinner() {
  return (
    <div className="flex items-center justify-center py-20">
      <div className="w-8 h-8 border-2 border-accent/30 border-t-accent rounded-full animate-spin" />
    </div>
  );
}

// ─── Main Component ─────────────────────────────────────────

export default function Jurisdictions() {
  const [currentCode, setCurrentCode] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [activeTab, setActiveTab] = useState<JurisdictionTab>("overview");
  const [showCreateModal, setShowCreateModal] = useState(false);

  // Reset tab when jurisdiction changes
  useEffect(() => {
    setActiveTab("overview");
  }, [currentCode]);

  // Always fetch all jurisdictions for stats
  const { data: allJurisdictions, refetch: refetchAll } = useApi(
    () => api.jurisdictions.list({ limit: "2000" }),
    []
  );

  // Fetch countries for root view
  const { data: countries, loading: countriesLoading, refetch: refetchCountries } = useApi(
    () => api.jurisdictions.list({ jurisdiction_type: "country", limit: "500" }),
    []
  );

  // Conditional fetches for drill-down
  const { data: current, loading: currentLoading } = useApi(
    () => currentCode ? api.jurisdictions.get(currentCode) : Promise.resolve(null as unknown as Jurisdiction),
    [currentCode]
  );

  const { data: children, loading: childrenLoading, refetch: refetchChildren } = useApi(
    () => currentCode ? api.jurisdictions.children(currentCode) : Promise.resolve([] as Jurisdiction[]),
    [currentCode]
  );

  const { data: ancestors, loading: ancestorsLoading } = useApi(
    () => currentCode ? api.jurisdictions.ancestors(currentCode) : Promise.resolve([] as Jurisdiction[]),
    [currentCode]
  );

  // All rates including inherited from parent jurisdictions (for overview)
  const { data: lookupRates, loading: lookupLoading } = useApi(
    () => currentCode ? api.rates.lookup(currentCode) : Promise.resolve(null as unknown as RateLookupResponse),
    [currentCode]
  );

  // Sample tax calculation for the combined overview
  const { data: sampleCalc, loading: sampleCalcLoading } = useApi(
    () => {
      if (!currentCode || !current) return Promise.resolve(null as unknown as TaxCalculationResponse);
      return api.tax.calculate({
        jurisdiction_code: currentCode,
        stay_date: new Date().toISOString().split("T")[0],
        nightly_rate: 200,
        currency: current.currency_code || "USD",
        nights: 3,
        property_type: "hotel",
      });
    },
    [currentCode, current]
  );

  // Regulatory monitoring sources
  const { data: sources, loading: sourcesLoading } = useApi(
    () => currentCode ? api.monitoring.sources({ jurisdiction_code: currentCode, limit: "2000" }) : Promise.resolve([] as MonitoredSource[]),
    [currentCode]
  );

  // Pending changes count for tab badge
  const { data: changesData } = useApi(
    () => currentCode ? api.monitoring.changes({ jurisdiction_code: currentCode, limit: "2000" }) : Promise.resolve([]),
    [currentCode]
  );
  const pendingChangesCount = (changesData || []).filter((c) => c.review_status === "pending").length;

  const isSubJurisdiction = current?.jurisdiction_type !== "country";

  // Stats from all jurisdictions
  const stats = useMemo(() => {
    const list = allJurisdictions || [];
    const counts = { countries: 0, regions: 0, cities: 0, active: 0 };
    for (const j of list) {
      if (j.jurisdiction_type === "country") counts.countries++;
      else if (["state", "province", "region"].includes(j.jurisdiction_type))
        counts.regions++;
      else if (["city", "district", "special_zone"].includes(j.jurisdiction_type))
        counts.cities++;
      if (j.status === "active") counts.active++;
    }
    return counts;
  }, [allJurisdictions]);

  // Filter countries by search
  const filteredCountries = useMemo(() => {
    const list = countries || [];
    if (!search.trim()) return list;
    const q = search.toLowerCase();
    return list.filter(
      (j) =>
        j.name.toLowerCase().includes(q) ||
        j.code.toLowerCase().includes(q) ||
        j.country_code.toLowerCase().includes(q)
    );
  }, [countries, search]);

  // Filter children by search (only relevant on overview tab)
  const filteredChildren = useMemo(() => {
    const list = children || [];
    if (!search.trim()) return list;
    const q = search.toLowerCase();
    return list.filter(
      (j) =>
        j.name.toLowerCase().includes(q) ||
        j.code.toLowerCase().includes(q)
    );
  }, [children, search]);

  const navigate = (code: string | null) => {
    setCurrentCode(code);
    setSearch("");
  };

  const totalJurisdictions = allJurisdictions?.length || 0;

  return (
    <PageTransition>
    <div className="p-4 sm:p-6 lg:p-10 max-w-[1400px]">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-4">
        <PageHeader
          title="Jurisdictions"
          description={`${totalJurisdictions} jurisdictions across ${stats.countries} countries`}
        />
        <button
          onClick={() => setShowCreateModal(true)}
          className="btn-primary px-4 py-2 text-sm flex-shrink-0"
        >
          {currentCode ? "+ Add Sub-Jurisdiction" : "+ Add Country"}
        </button>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5 mb-8">
        <StatCard label="Countries" value={stats.countries} sub="Sovereign states" />
        <StatCard label="Regions" value={stats.regions} sub="States & provinces" />
        <StatCard label="Cities" value={stats.cities} sub="Local jurisdictions" />
        <StatCard label="Active" value={stats.active} accent="success" sub="Currently active" />
      </div>

      {/* Breadcrumb */}
      {currentCode && (
        <Breadcrumb
          ancestors={ancestors || []}
          current={current}
          loading={ancestorsLoading || currentLoading}
          onNavigate={navigate}
        />
      )}

      {/* Search + Back (root and overview only) */}
      {(currentCode === null || activeTab === "overview") && (
        <div className="flex gap-3 mb-6">
          <input
            type="text"
            placeholder={currentCode ? "Filter sub-jurisdictions..." : "Search countries..."}
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="input-field w-full sm:w-72"
          />
          {currentCode && (
            <button
              onClick={() => {
                const parentCode = ancestors && ancestors.length > 0
                  ? ancestors[ancestors.length - 1].code
                  : null;
                navigate(parentCode);
              }}
              className="btn-secondary flex items-center gap-2"
            >
              <ArrowLeft className="w-4 h-4" />
              Back
            </button>
          )}
        </div>
      )}

      {/* Content */}
      {currentCode === null ? (
        <RootView
          countries={filteredCountries}
          loading={countriesLoading}
          onSelect={navigate}
        />
      ) : currentLoading ? (
        <Spinner />
      ) : current ? (
        <div className="space-y-6">
          {/* Tab Bar */}
          <div className="flex gap-1 bg-surface rounded-lg p-1 w-fit border border-border overflow-x-auto scrollbar-hide">
            {(current?.jurisdiction_type === "country" ? TABS_COUNTRY : TABS_DEFAULT).map((t) => (
              <button
                key={t.key}
                onClick={() => setActiveTab(t.key)}
                className={`px-5 py-2 text-sm font-medium rounded-md cursor-pointer transition-all flex items-center gap-2 flex-shrink-0 ${
                  activeTab === t.key
                    ? "bg-card text-text shadow-sm border border-border"
                    : "text-dim hover:text-muted"
                }`}
              >
                {t.label}
                {t.key === "changes" && pendingChangesCount > 0 && (
                  <span className="bg-warning text-white text-xs font-bold px-1.5 py-0.5 rounded-full min-w-[20px] text-center">
                    {pendingChangesCount}
                  </span>
                )}
              </button>
            ))}
          </div>

          {/* Tab Content */}
          <div key={activeTab} className="animate-fadeIn">
          {activeTab === "overview" && (
            <OverviewTab
              current={current}
              children={filteredChildren}
              childrenLoading={childrenLoading}
              onNavigate={navigate}
              ancestors={ancestors || []}
              lookupRates={lookupRates}
              lookupLoading={lookupLoading}
              sampleCalc={sampleCalc}
              sampleCalcLoading={sampleCalcLoading}
              isSubJurisdiction={!!isSubJurisdiction}
              sources={sources || []}
              sourcesLoading={sourcesLoading}
            />
          )}
          {activeTab === "rates" && <RatesTab jurisdictionCode={currentCode} />}
          {activeTab === "rules" && <RulesTab jurisdictionCode={currentCode} />}
          {activeTab === "changes" && <ChangesTab jurisdictionCode={currentCode} />}
          {activeTab === "monitoring" && <MonitoringTab jurisdictionCode={currentCode} />}
          {activeTab === "discovery" && current?.jurisdiction_type === "country" && (
            <DiscoveryTab jurisdictionCode={currentCode} countryName={current.name} />
          )}
          </div>
        </div>
      ) : null}

      <CreateJurisdictionModal
        open={showCreateModal}
        parentCode={currentCode}
        parentCountryCode={current?.country_code}
        defaultType={currentCode ? "city" : "country"}
        onClose={() => setShowCreateModal(false)}
        onCreated={() => {
          refetchAll();
          refetchCountries();
          if (currentCode) refetchChildren();
        }}
      />
    </div>
    </PageTransition>
  );
}

// ─── Breadcrumb ─────────────────────────────────────────────

function Breadcrumb({
  ancestors,
  current,
  loading,
  onNavigate,
}: {
  ancestors: Jurisdiction[];
  current: Jurisdiction | null;
  loading: boolean;
  onNavigate: (code: string | null) => void;
}) {
  return (
    <div className="flex items-center gap-1.5 mb-6 text-sm flex-wrap bg-surface/50 border border-border rounded-lg px-4 py-2.5">
      <button
        onClick={() => onNavigate(null)}
        className="flex items-center gap-1.5 text-accent hover:text-accent/80 transition-colors"
      >
        <Home className="w-4 h-4" />
        <span>All Countries</span>
      </button>

      {ancestors.map((a) => (
        <span key={a.code} className="flex items-center gap-1.5">
          <ChevronRight className="w-3.5 h-3.5 text-dim" />
          <button
            onClick={() => onNavigate(a.code)}
            className="text-accent hover:text-accent/80 transition-colors"
          >
            {a.name}
          </button>
        </span>
      ))}

      {current && !loading && (
        <span className="flex items-center gap-1.5">
          <ChevronRight className="w-3.5 h-3.5 text-dim" />
          <span className="font-semibold text-text">{current.name}</span>
        </span>
      )}
    </div>
  );
}

// ─── Root View (Country Grid) ───────────────────────────────

function RootView({
  countries,
  loading,
  onSelect,
}: {
  countries: Jurisdiction[];
  loading: boolean;
  onSelect: (code: string) => void;
}) {
  if (loading) return <Spinner />;

  if (countries.length === 0) {
    return (
      <Card className="py-16 text-center text-sm text-dim">
        No countries found
      </Card>
    );
  }

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
      {countries.map((country) => (
        <CountryCard
          key={country.code}
          jurisdiction={country}
          onClick={() => onSelect(country.code)}
        />
      ))}
    </div>
  );
}

function CountryCard({
  jurisdiction,
  onClick,
}: {
  jurisdiction: Jurisdiction;
  onClick: () => void;
}) {
  const Icon = TYPE_ICONS[jurisdiction.jurisdiction_type] || Globe;

  return (
    <Card
      className="p-5 cursor-pointer hover:border-accent/30 hover:bg-surface/50 transition-all group"
    >
      <div onClick={onClick} className="flex items-center gap-4">
        <div className="w-10 h-10 rounded-lg bg-accent/10 flex items-center justify-center flex-shrink-0 group-hover:bg-accent/15 transition-colors">
          <Icon className="w-5 h-5 text-accent" />
        </div>
        <div className="min-w-0 flex-1">
          <div className="font-semibold text-text truncate">{jurisdiction.name}</div>
          <div className="flex items-center gap-2 mt-1">
            <span className="font-mono text-xs text-accent bg-accent/10 px-2 py-0.5 rounded">
              {jurisdiction.code}
            </span>
            <span className="text-xs text-dim">{jurisdiction.currency_code}</span>
          </div>
        </div>
        <ChevronRight className="w-4 h-4 text-dim group-hover:text-accent transition-colors flex-shrink-0" />
      </div>
    </Card>
  );
}
