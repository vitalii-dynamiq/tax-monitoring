import { useState } from "react";
import PageHeader from "../components/PageHeader";
import PageTransition from "../components/PageTransition";
import Card from "../components/Card";
import Badge from "../components/Badge";
import {
  api,
  type TaxCalculationRequest,
  type TaxCalculationResponse,
  type TaxComponent,
} from "../lib/api";
import { formatCurrency } from "../lib/utils";

const PRESETS: (Partial<TaxCalculationRequest> & { label: string })[] = [
  { label: "NYC Hotel", jurisdiction_code: "US-NY-NYC", nightly_rate: 300, currency: "USD", nights: 5, property_type: "hotel", star_rating: 4 },
  { label: "Dubai 5-Star", jurisdiction_code: "AE-DU", nightly_rate: 800, currency: "AED", nights: 3, property_type: "hotel", star_rating: 5 },
  { label: "Barcelona", jurisdiction_code: "ES-CT-BCN", nightly_rate: 200, currency: "EUR", nights: 4, property_type: "hotel", star_rating: 4, number_of_guests: 2 },
  { label: "Tokyo Luxury", jurisdiction_code: "JP-13-TYO", nightly_rate: 45000, currency: "JPY", nights: 3, property_type: "hotel", star_rating: 5 },
  { label: "Paris STR", jurisdiction_code: "FR-IDF-PAR", nightly_rate: 150, currency: "EUR", nights: 5, property_type: "short_term_rental" },
  { label: "Amsterdam", jurisdiction_code: "NL-NH-AMS", nightly_rate: 180, currency: "EUR", nights: 4, property_type: "short_term_rental" },
  { label: "Rome Hotel", jurisdiction_code: "IT-RM-ROM", nightly_rate: 200, currency: "EUR", nights: 4, property_type: "hotel", star_rating: 4 },
  { label: "Chicago", jurisdiction_code: "US-IL-CHI", nightly_rate: 250, currency: "USD", nights: 2, property_type: "hotel", star_rating: 4 },
];

const TODAY = new Date().toISOString().split("T")[0];

function rateDescription(c: TaxComponent, currency: string): string {
  if (c.rate_type === "percentage" && c.rate != null) {
    if (c.rate === 0) return "0% (exempt)";
    return `${(c.rate * 100).toFixed(2)}% of ${formatCurrency(c.taxable_amount ?? 0, currency)}`;
  }
  if (c.rate_type === "flat" && c.rate != null) {
    return `${formatCurrency(c.rate, currency)} per night`;
  }
  if (c.rate_type === "tiered") return "tiered rate";
  return c.rate_type;
}

export default function Calculator() {
  const [form, setForm] = useState<TaxCalculationRequest>({
    jurisdiction_code: "US-NY-NYC",
    stay_date: TODAY,
    nightly_rate: 300,
    currency: "USD",
    nights: 5,
    property_type: "hotel",
    star_rating: 4,
  });
  const [result, setResult] = useState<TaxCalculationResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const calculate = () => {
    if (!form.jurisdiction_code) return;
    setLoading(true);
    setError(null);
    api.tax
      .calculate(form)
      .then(setResult)
      .catch((e) => {
        setError(e.message);
        setResult(null);
      })
      .finally(() => setLoading(false));
  };

  const applyPreset = (preset: (typeof PRESETS)[number]) => {
    const newForm: TaxCalculationRequest = {
      ...form,
      jurisdiction_code: preset.jurisdiction_code!,
      nightly_rate: preset.nightly_rate!,
      currency: preset.currency!,
      nights: preset.nights!,
      property_type: preset.property_type,
      star_rating: preset.star_rating,
      number_of_guests: preset.number_of_guests,
    };
    setForm(newForm);
    setResult(null);
    setError(null);
    setLoading(true);
    api.tax
      .calculate(newForm)
      .then(setResult)
      .catch((e) => {
        setError(e.message);
        setResult(null);
      })
      .finally(() => setLoading(false));
  };

  const update = (key: string, value: string | number | boolean | undefined) => {
    setForm((f) => ({ ...f, [key]: value }));
  };

  const subtotal = form.nightly_rate * form.nights;
  const effectiveRate = result
    ? result.tax_breakdown.effective_rate > 0
      ? result.tax_breakdown.effective_rate
      : subtotal > 0
        ? result.tax_breakdown.total_tax / subtotal
        : 0
    : 0;

  return (
    <PageTransition><div className="p-4 sm:p-6 lg:p-10 max-w-[1400px]">
      <PageHeader
        title="Tax Calculator"
        description="Calculate accommodation taxes for any jurisdiction in real time"
      />

      <div className="mb-6">
        <div className="text-xs font-semibold uppercase tracking-widest text-dim mb-3">Quick Presets</div>
        <div className="flex gap-2 flex-nowrap overflow-x-auto scrollbar-hide pb-1">
          {PRESETS.map((p) => (
            <button
              key={p.label}
              onClick={() => applyPreset(p)}
              className={`flex-shrink-0 px-4 py-2 text-sm font-medium rounded-md border transition-all duration-150 ${
                form.jurisdiction_code === p.jurisdiction_code
                  ? "bg-accent/15 border-accent/30 text-accent"
                  : "bg-surface border-border text-muted hover:text-text hover:border-border-light"
              }`}
            >
              {p.label}
            </button>
          ))}
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
        <Card className="lg:col-span-2">
          <div className="px-4 sm:px-6 py-4 border-b border-border">
            <span className="text-base font-semibold text-text">Booking Details</span>
          </div>
          <div className="p-4 sm:p-6">
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-x-5 gap-y-5">
              <Field label="Jurisdiction Code" required>
                <input
                  type="text"
                  value={form.jurisdiction_code}
                  onChange={(e) => update("jurisdiction_code", e.target.value)}
                  placeholder="e.g. US-NY-NYC"
                  className="input-field font-mono"
                />
              </Field>
              <Field label="Stay Date" required>
                <input
                  type="date"
                  value={form.stay_date}
                  onChange={(e) => update("stay_date", e.target.value)}
                  className="input-field"
                />
              </Field>
              <Field label="Nights" required>
                <input
                  type="number"
                  min={1}
                  value={form.nights}
                  onChange={(e) => update("nights", parseInt(e.target.value) || 1)}
                  className="input-field"
                />
              </Field>
              <Field label="Nightly Rate" required>
                <input
                  type="number"
                  min={0}
                  step={0.01}
                  value={form.nightly_rate}
                  onChange={(e) => update("nightly_rate", parseFloat(e.target.value) || 0)}
                  className="input-field font-mono"
                />
              </Field>
              <Field label="Currency" required>
                <input
                  type="text"
                  value={form.currency}
                  onChange={(e) => update("currency", e.target.value.toUpperCase())}
                  maxLength={3}
                  className="input-field font-mono"
                />
              </Field>
              <Field label="Property Type">
                <select
                  value={form.property_type || ""}
                  onChange={(e) => update("property_type", e.target.value || undefined)}
                  className="input-field"
                >
                  <option value="">Not specified</option>
                  <option value="hotel">Hotel</option>
                  <option value="short_term_rental">Short-term Rental</option>
                  <option value="bed_and_breakfast">B&B</option>
                  <option value="hostel">Hostel</option>
                  <option value="resort">Resort</option>
                  <option value="serviced_apartment">Serviced Apartment</option>
                </select>
              </Field>
              <Field label="Star Rating">
                <select
                  value={form.star_rating ?? ""}
                  onChange={(e) =>
                    update("star_rating", e.target.value ? parseInt(e.target.value) : undefined)
                  }
                  className="input-field"
                >
                  <option value="">Not rated</option>
                  {[1, 2, 3, 4, 5].map((s) => (
                    <option key={s} value={s}>
                      {s} Star
                    </option>
                  ))}
                </select>
              </Field>
              <Field label="Guests">
                <input
                  type="number"
                  min={1}
                  value={form.number_of_guests ?? ""}
                  onChange={(e) =>
                    update("number_of_guests", e.target.value ? parseInt(e.target.value) : undefined)
                  }
                  placeholder="Optional"
                  className="input-field"
                />
              </Field>
              <Field label="Guest Type">
                <select
                  value={form.guest_type || ""}
                  onChange={(e) => update("guest_type", e.target.value || undefined)}
                  className="input-field"
                >
                  <option value="">Not specified</option>
                  <option value="tourist">Tourist</option>
                  <option value="business">Business</option>
                  <option value="resident">Resident</option>
                </select>
              </Field>
            </div>
            <div className="mt-6 flex items-center gap-3">
              <button
                onClick={calculate}
                disabled={loading || !form.jurisdiction_code}
                className="btn-primary"
              >
                {loading ? "Calculating..." : "Calculate Tax"}
              </button>
              {result && (
                <span className="text-xs text-dim hidden sm:inline">
                  Calculated in real time against production rules
                </span>
              )}
            </div>
          </div>
        </Card>

        <div className="space-y-5">
          <Card>
            <div className="px-4 sm:px-6 py-4 border-b border-border">
              <span className="text-base font-semibold text-text">Result</span>
            </div>
            <div className="p-4 sm:p-6">
              {error && (
                <div className="bg-danger/10 border border-danger/20 rounded-lg px-4 py-3 text-sm text-danger mb-4">
                  {error}
                </div>
              )}
              {result ? (
                <div className="space-y-5">
                  <div>
                    <div className="text-xs font-semibold uppercase tracking-widest text-dim mb-1">Jurisdiction</div>
                    <div className="text-base font-mono font-semibold text-accent">
                      {result.jurisdiction.code}
                    </div>
                    <div className="text-sm text-dim mt-0.5">{result.jurisdiction.name}</div>
                  </div>

                  <div className="h-px bg-border" />

                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                    <div>
                      <div className="text-xs font-semibold uppercase tracking-widest text-dim mb-1">Subtotal</div>
                      <div className="text-lg sm:text-xl font-bold font-mono">
                        {formatCurrency(subtotal, form.currency)}
                      </div>
                    </div>
                    <div>
                      <div className="text-xs font-semibold uppercase tracking-widest text-dim mb-1">Total Tax</div>
                      <div className="text-lg sm:text-xl font-bold font-mono text-warning">
                        {formatCurrency(result.tax_breakdown.total_tax, form.currency)}
                      </div>
                    </div>
                  </div>

                  <div>
                    <div className="text-xs font-semibold uppercase tracking-widest text-dim mb-1">Effective Rate</div>
                    <div className="text-lg font-bold font-mono">
                      {(effectiveRate * 100).toFixed(2)}%
                    </div>
                  </div>

                  <div className="h-px bg-border" />

                  <div>
                    <div className="text-xs font-semibold uppercase tracking-widest text-dim mb-1">Total with Tax</div>
                    <div className="text-xl sm:text-2xl font-bold font-mono text-success">
                      {formatCurrency(result.total_with_tax, form.currency)}
                    </div>
                  </div>
                </div>
              ) : (
                <div className="text-sm text-dim py-8 text-center">
                  Select a preset or enter booking details
                </div>
              )}
            </div>
          </Card>
        </div>
      </div>

      {result && result.tax_breakdown.components.length > 0 && (
        <Card className="mt-5">
          <div className="px-4 sm:px-6 py-4 border-b border-border">
            <span className="text-base font-semibold text-text">
              Tax Components ({result.tax_breakdown.components.length})
            </span>
          </div>
          <div className="divide-y divide-border">
            {result.tax_breakdown.components.map((c, i) => (
              <div
                key={i}
                className="px-4 sm:px-6 py-3 sm:py-4 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-1.5 sm:gap-3 hover:bg-surface transition-colors"
              >
                <div className="flex items-center gap-2 sm:gap-3 min-w-0">
                  <Badge value={c.rate_type} />
                  <div className="min-w-0">
                    <div className="text-sm font-medium text-text">{c.name}</div>
                    {c.legal_reference && (
                      <div className="text-xs text-dim mt-0.5">{c.legal_reference}</div>
                    )}
                  </div>
                </div>
                <div className="sm:text-right flex-shrink-0 pl-7 sm:pl-0">
                  <div className="text-sm font-mono font-semibold text-text">
                    {formatCurrency(c.tax_amount, form.currency)}
                  </div>
                  <div className="text-xs text-dim font-mono mt-0.5">
                    {rateDescription(c, form.currency)}
                  </div>
                </div>
              </div>
            ))}
          </div>
        </Card>
      )}

      {result && result.rules_applied.length > 0 && (
        <Card className="mt-5">
          <div className="px-4 sm:px-6 py-4 border-b border-border">
            <span className="text-base font-semibold text-text">
              Rules Evaluated ({result.rules_applied.length})
            </span>
          </div>
          <div className="divide-y divide-border">
            {result.rules_applied.map((r, i) => (
              <div
                key={i}
                className="px-4 sm:px-6 py-3 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-1.5 sm:gap-3"
              >
                <div className="flex items-center gap-2 sm:gap-3 min-w-0">
                  <Badge value={r.rule_type} />
                  <span className="text-sm text-text">{r.name}</span>
                </div>
                <span
                  className={`self-start sm:self-auto text-xs font-semibold px-2.5 py-1 rounded-md uppercase flex-shrink-0 ${
                    r.result === "applied"
                      ? "bg-success/15 text-success"
                      : r.result === "exempted"
                        ? "bg-warning/15 text-warning"
                        : "bg-surface text-dim"
                  }`}
                >
                  {r.result}
                </span>
              </div>
            ))}
          </div>
        </Card>
      )}
    </div></PageTransition>
  );
}

function Field({
  label,
  required,
  children,
}: {
  label: string;
  required?: boolean;
  children: React.ReactNode;
}) {
  return (
    <div>
      <label className="block text-xs font-semibold uppercase tracking-widest text-dim mb-2">
        {label}
        {required && <span className="text-danger ml-0.5">*</span>}
      </label>
      {children}
    </div>
  );
}
