import { useState, useEffect, useRef } from "react";
import { api, type JurisdictionCreate } from "../lib/api";
import { useToast } from "../hooks/useToast";

const JURISDICTION_TYPES = [
  { value: "country", label: "Country" },
  { value: "state", label: "State" },
  { value: "province", label: "Province" },
  { value: "region", label: "Region" },
  { value: "city", label: "City" },
  { value: "district", label: "District" },
  { value: "special_zone", label: "Special Zone" },
];

const COMMON_CURRENCIES = [
  "USD", "EUR", "GBP", "JPY", "AED", "AUD", "CAD", "CHF", "CNY",
  "CZK", "DKK", "HKD", "HUF", "IDR", "ILS", "INR", "KRW", "MXN",
  "MYR", "NOK", "NZD", "PHP", "PLN", "SEK", "SGD", "THB", "TRY",
  "TWD", "ZAR", "BRL",
];

interface CreateJurisdictionModalProps {
  open: boolean;
  parentCode?: string | null;
  parentCountryCode?: string;
  defaultType?: string;
  onClose: () => void;
  onCreated: () => void;
}

export default function CreateJurisdictionModal({
  open,
  parentCode,
  parentCountryCode,
  defaultType = "country",
  onClose,
  onCreated,
}: CreateJurisdictionModalProps) {
  const { toast } = useToast();
  const codeInputRef = useRef<HTMLInputElement>(null);
  const isAddingCountry = !parentCode;

  const [code, setCode] = useState("");
  const [name, setName] = useState("");
  const [localName, setLocalName] = useState("");
  const [jurisdictionType, setJurisdictionType] = useState(defaultType);
  const [countryCode, setCountryCode] = useState(parentCountryCode || "");
  const [currencyCode, setCurrencyCode] = useState("");
  const [timezone, setTimezone] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Auto-focus code input when modal opens
  useEffect(() => {
    if (open) {
      setTimeout(() => codeInputRef.current?.focus(), 0);
    }
  }, [open]);

  // Close on Escape key
  useEffect(() => {
    if (!open) return;
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [open, onClose]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    setError(null);

    const data: JurisdictionCreate = {
      code: code.toUpperCase(),
      name,
      jurisdiction_type: jurisdictionType,
      country_code: isAddingCountry ? code.toUpperCase() : (countryCode || parentCountryCode || ""),
      currency_code: currencyCode.toUpperCase(),
    };

    if (localName) data.local_name = localName;
    if (parentCode) data.parent_code = parentCode;
    if (timezone) data.timezone = timezone;

    try {
      await api.jurisdictions.create(data);
      toast("Jurisdiction created", "success");
      // Reset form
      setCode("");
      setName("");
      setLocalName("");
      setTimezone("");
      setCurrencyCode("");
      onCreated();
      onClose();
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : "Failed to create jurisdiction";
      setError(message);
      toast(message, "error");
    } finally {
      setSaving(false);
    }
  };

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div className="absolute inset-0 bg-black/30" onClick={onClose} />
      <div className="relative bg-card border border-border rounded-xl shadow-lg p-6 max-w-lg w-full mx-4 max-h-[90vh] overflow-y-auto">
        <h3 className="text-lg font-semibold text-text mb-1">
          {isAddingCountry ? "Add Country" : "Add Sub-Jurisdiction"}
        </h3>
        <p className="text-sm text-dim mb-5">
          {isAddingCountry
            ? "Add a new country to the platform. You can then discover its sub-jurisdictions."
            : `Add a sub-jurisdiction under ${parentCode}.`}
        </p>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-xs text-dim mb-1">
                Code <span className="text-danger">*</span>
              </label>
              <input
                ref={codeInputRef}
                type="text"
                value={code}
                onChange={(e) => setCode(e.target.value)}
                placeholder={isAddingCountry ? "BR" : `${parentCode}-SAO`}
                className="input-field w-full text-sm font-mono uppercase"
                required
              />
            </div>
            <div>
              <label className="block text-xs text-dim mb-1">
                Type <span className="text-danger">*</span>
              </label>
              <select
                value={jurisdictionType}
                onChange={(e) => setJurisdictionType(e.target.value)}
                className="input-field w-full text-sm"
                required
              >
                {JURISDICTION_TYPES.map((t) => (
                  <option key={t.value} value={t.value}>
                    {t.label}
                  </option>
                ))}
              </select>
            </div>
          </div>

          <div>
            <label className="block text-xs text-dim mb-1">
              Name <span className="text-danger">*</span>
            </label>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g. Brazil"
              className="input-field w-full text-sm"
              required
            />
          </div>

          <div>
            <label className="block text-xs text-dim mb-1">Local Name</label>
            <input
              type="text"
              value={localName}
              onChange={(e) => setLocalName(e.target.value)}
              placeholder="e.g. Brasil"
              className="input-field w-full text-sm"
            />
          </div>

          <div className="grid grid-cols-2 gap-4">
            {!isAddingCountry && (
              <div>
                <label className="block text-xs text-dim mb-1">Country Code</label>
                <input
                  type="text"
                  value={countryCode || parentCountryCode || ""}
                  onChange={(e) => setCountryCode(e.target.value)}
                  className="input-field w-full text-sm font-mono uppercase"
                  maxLength={2}
                  required
                />
              </div>
            )}
            <div>
              <label className="block text-xs text-dim mb-1">
                Currency <span className="text-danger">*</span>
              </label>
              <select
                value={currencyCode}
                onChange={(e) => setCurrencyCode(e.target.value)}
                className="input-field w-full text-sm"
                required
              >
                <option value="">Select currency</option>
                {COMMON_CURRENCIES.map((c) => (
                  <option key={c} value={c}>
                    {c}
                  </option>
                ))}
              </select>
            </div>
          </div>

          <div>
            <label className="block text-xs text-dim mb-1">Timezone</label>
            <input
              type="text"
              value={timezone}
              onChange={(e) => setTimezone(e.target.value)}
              placeholder="e.g. America/Sao_Paulo"
              className="input-field w-full text-sm"
            />
          </div>

          {error && (
            <div className="text-sm text-danger bg-danger/5 border border-danger/20 rounded-lg px-4 py-2">
              {error}
            </div>
          )}

          <div className="flex justify-end gap-3 pt-2">
            <button
              type="button"
              onClick={onClose}
              className="btn-secondary px-4 py-2 text-sm"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={saving || !code || !name || !currencyCode}
              className="btn-primary px-4 py-2 text-sm"
            >
              {saving ? "Creating..." : "Create"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
