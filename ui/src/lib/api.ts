function getAuthHeaders(): Record<string, string> {
  const token = localStorage.getItem("taxlens_token");
  if (token) {
    return { Authorization: `Bearer ${token}` };
  }
  return {};
}

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(path, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...getAuthHeaders(),
      ...options?.headers,
    },
  });
  if (!res.ok) {
    if (res.status === 401 && !path.startsWith("/v1/auth/")) {
      localStorage.removeItem("taxlens_token");
      window.dispatchEvent(new Event("auth:logout"));
    }
    const body = await res.json().catch(() => null);
    throw new Error(body?.detail || `${res.status} ${res.statusText}`);
  }
  if (res.status === 204 || res.headers.get("content-length") === "0") {
    return undefined as T;
  }
  return res.json();
}

// --- Types ---

export interface Jurisdiction {
  id: number;
  code: string;
  name: string;
  local_name: string | null;
  jurisdiction_type: string;
  parent_id: number | null;
  country_code: string;
  subdivision_code: string | null;
  timezone: string | null;
  currency_code: string;
  path: string | null;
  status: string;
  metadata: Record<string, unknown> | null;
  created_at: string;
  updated_at: string;
}

export interface TaxRate {
  id: number;
  jurisdiction_code: string;
  tax_category_code: string;
  rate_type: "percentage" | "flat" | "tiered";
  rate_value: number | null;
  currency_code: string | null;
  tiers: Record<string, unknown>[] | null;
  tier_type: string | null;
  enacted_date: string | null;
  effective_start: string;
  effective_end: string | null;
  applicability_start: string | null;
  announcement_date: string | null;
  calculation_order: number;
  base_includes: string[] | null;
  legal_reference: string | null;
  legal_uri: string | null;
  source_url: string | null;
  authority_name: string | null;
  status: string;
  created_by: string | null;
  reviewed_by: string | null;
  reviewed_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface TaxRule {
  id: number;
  tax_rate_id: number | null;
  jurisdiction_code: string;
  rule_type: string;
  priority: number;
  name: string;
  description: string | null;
  conditions: Record<string, unknown> | null;
  action: Record<string, unknown> | null;
  effective_start: string;
  effective_end: string | null;
  enacted_date: string | null;
  legal_reference: string | null;
  legal_uri: string | null;
  authority_name: string | null;
  status: string;
  created_by: string | null;
  reviewed_by: string | null;
  reviewed_at: string | null;
  created_at: string;
  updated_at: string;
  supersedes_id: number | null;
}

export interface TaxComponent {
  name: string;
  category_code: string;
  jurisdiction_code: string;
  jurisdiction_level: string;
  rate: number | null;
  rate_type: string;
  taxable_amount: number | null;
  tax_amount: number;
  legal_reference: string | null;
  authority: string | null;
}

export interface TaxBreakdown {
  components: TaxComponent[];
  total_tax: number;
  effective_rate: number;
  currency: string;
}

export interface RuleTraceEntry {
  rule_id: number;
  name: string;
  rule_type: string;
  result: string;
}

export interface TaxCalculationResponse {
  calculation_id: string;
  jurisdiction: { code: string; name: string; path: string };
  input: Record<string, unknown>;
  tax_breakdown: TaxBreakdown;
  total_with_tax: number;
  rules_applied: RuleTraceEntry[];
  calculated_at: string;
  data_version: string | null;
}

export interface TaxCalculationRequest {
  jurisdiction_code: string;
  stay_date: string;
  checkout_date?: string;
  nightly_rate: number;
  currency: string;
  property_type?: string;
  star_rating?: number;
  guest_type?: string;
  guest_age?: number;
  guest_nationality?: string;
  nights: number;
  number_of_guests?: number;
  is_marketplace?: boolean;
  platform_type?: string;
  is_bundled?: boolean;
}

export interface MonitoredSource {
  id: number;
  jurisdiction_code: string | null;
  url: string; // stores domain (e.g. "nyc.gov")
  source_type: string;
  language: string | null;
  check_frequency_days: number;
  status: string;
  last_checked_at: string | null;
  last_content_hash: string | null;
  metadata: Record<string, unknown> | null;
  created_at: string;
  updated_at: string;
}

export interface MonitoredSourceCreate {
  jurisdiction_code: string;
  url: string; // domain
  source_type: string;
  language?: string;
}

export interface JurisdictionCreate {
  code: string;
  name: string;
  local_name?: string;
  jurisdiction_type: string;
  parent_code?: string;
  country_code: string;
  subdivision_code?: string;
  timezone?: string;
  currency_code: string;
  status?: string;
  metadata?: Record<string, unknown>;
}

export interface DetectedChange {
  id: number;
  source_id: number | null;
  jurisdiction_id: number | null;
  jurisdiction_code: string | null;
  change_type: string;
  detected_at: string;
  extracted_data: Record<string, unknown>;
  confidence: number;
  source_quote: string | null;
  source_snapshot_url: string | null;
  review_status: string;
  reviewed_by: string | null;
  reviewed_at: string | null;
  review_notes: string | null;
  applied_rate_id: number | null;
  applied_rule_id: number | null;
  created_at: string;
}

export interface AuditLogEntry {
  id: number;
  entity_type: string;
  entity_id: number;
  action: string;
  old_values: Record<string, unknown> | null;
  new_values: Record<string, unknown> | null;
  changed_by: string;
  change_source: string;
  change_reason: string | null;
  source_reference: string | null;
  created_at: string;
}

export interface MonitoringJob {
  id: number;
  jurisdiction_id: number;
  jurisdiction_code: string | null;
  job_type: "monitoring" | "discovery";
  status: "pending" | "running" | "completed" | "failed" | "cancelled";
  trigger_type: "manual" | "scheduled";
  triggered_by: string;
  started_at: string | null;
  completed_at: string | null;
  result_summary: Record<string, unknown> | null;
  changes_detected: number;
  error_message: string | null;
  created_at: string;
  updated_at: string;
}

export interface MonitoringSchedule {
  id: number;
  jurisdiction_id: number;
  jurisdiction_code: string | null;
  enabled: boolean;
  cadence: "daily" | "weekly" | "monthly" | "custom";
  cron_expression: string | null;
  last_run_at: string | null;
  next_run_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface ChangeReviewRequest {
  review_status: "approved" | "rejected" | "needs_review";
  reviewed_by?: string;
  review_notes?: string;
}

export interface HealthResponse {
  status: string;
  version: string;
  database: string;
  scheduler?: string;
  ai_configured?: boolean;
}

export interface RateLookupResponse {
  jurisdiction: { code: string; name: string; path: string };
  date: string;
  rates: TaxRate[];
  combined_percentage_rate: number;
}

export interface ApiKeyResponse {
  id: number;
  name: string;
  key_prefix: string;
  is_active: boolean;
  last_used_at: string | null;
  expires_at: string | null;
  created_at: string;
}

export interface CreateApiKeyResponse extends ApiKeyResponse {
  raw_key: string;
}

// --- API functions ---

export const api = {
  health: () => request<HealthResponse>("/health"),

  jurisdictions: {
    list: (params?: Record<string, string>) =>
      request<Jurisdiction[]>(`/v1/jurisdictions?${new URLSearchParams(params)}`),
    get: (code: string) => request<Jurisdiction>(`/v1/jurisdictions/${code}`),
    children: (code: string) => request<Jurisdiction[]>(`/v1/jurisdictions/${code}/children`),
    ancestors: (code: string) => request<Jurisdiction[]>(`/v1/jurisdictions/${code}/ancestors`),
    create: (data: JurisdictionCreate) =>
      request<Jurisdiction>("/v1/jurisdictions", {
        method: "POST",
        body: JSON.stringify(data),
      }),
  },

  rates: {
    list: (params?: Record<string, string>) =>
      request<TaxRate[]>(`/v1/rates?${new URLSearchParams(params)}`),
    get: (id: number) => request<TaxRate>(`/v1/rates/${id}`),
    lookup: (jurisdictionCode: string, date?: string) => {
      const params = new URLSearchParams({ jurisdiction_code: jurisdictionCode });
      if (date) params.set("effective_date", date);
      return request<RateLookupResponse>(`/v1/rates/lookup?${params}`);
    },
  },

  rules: {
    list: (params?: Record<string, string>) =>
      request<TaxRule[]>(`/v1/rules?${new URLSearchParams(params)}`),
    get: (id: number) => request<TaxRule>(`/v1/rules/${id}`),
  },

  tax: {
    calculate: (body: TaxCalculationRequest) =>
      request<TaxCalculationResponse>("/v1/tax/calculate", {
        method: "POST",
        body: JSON.stringify(body),
      }),
  },

  monitoring: {
    sources: (params?: Record<string, string>) =>
      request<MonitoredSource[]>(`/v1/monitoring/sources?${new URLSearchParams(params)}`),
    createSource: (data: MonitoredSourceCreate) =>
      request<MonitoredSource>("/v1/monitoring/sources", {
        method: "POST",
        body: JSON.stringify(data),
      }),
    changes: (params?: Record<string, string>) =>
      request<DetectedChange[]>(`/v1/monitoring/changes?${new URLSearchParams(params)}`),
    reviewChange: (id: number, review: ChangeReviewRequest) =>
      request<DetectedChange>(`/v1/monitoring/changes/${id}/review`, {
        method: "POST",
        body: JSON.stringify(review),
      }),
    triggerRun: (jurisdictionCode: string) =>
      request<MonitoringJob>(`/v1/monitoring/jobs/${jurisdictionCode}/run`, {
        method: "POST",
      }),
    listJobs: (params?: Record<string, string>) =>
      request<MonitoringJob[]>(`/v1/monitoring/jobs?${new URLSearchParams(params)}`),
    getJob: (jobId: number) => request<MonitoringJob>(`/v1/monitoring/jobs/${jobId}`),
    getSchedule: (jurisdictionCode: string) =>
      request<MonitoringSchedule>(`/v1/monitoring/schedules/${jurisdictionCode}`),
    updateSchedule: (jurisdictionCode: string, data: Partial<MonitoringSchedule>) =>
      request<MonitoringSchedule>(`/v1/monitoring/schedules/${jurisdictionCode}`, {
        method: "PUT",
        body: JSON.stringify(data),
      }),
    listSchedules: (params?: Record<string, string>) =>
      request<MonitoringSchedule[]>(`/v1/monitoring/schedules?${new URLSearchParams(params)}`),
  },

  discovery: {
    triggerRun: (countryCode: string) =>
      request<MonitoringJob>(`/v1/monitoring/discovery/${countryCode}/run`, {
        method: "POST",
      }),
    listJobs: (params?: Record<string, string>) =>
      request<MonitoringJob[]>(`/v1/monitoring/discovery/jobs?${new URLSearchParams(params)}`),
  },

  audit: {
    list: (params?: Record<string, string>) =>
      request<AuditLogEntry[]>(`/v1/audit?${new URLSearchParams(params)}`),
  },

  apiKeys: {
    list: () => request<ApiKeyResponse[]>("/v1/api-keys"),
    create: (body: { name: string; expires_at?: string }) =>
      request<CreateApiKeyResponse>("/v1/api-keys", {
        method: "POST",
        body: JSON.stringify(body),
      }),
    revoke: (id: number) =>
      request<void>(`/v1/api-keys/${id}`, { method: "DELETE" }),
  },
};
