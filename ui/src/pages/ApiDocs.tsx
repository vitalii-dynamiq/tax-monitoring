import { useState, useEffect, useRef, useCallback } from "react";
import { cn } from "../lib/utils";
import PageTransition from "../components/PageTransition";
import { Check, Copy } from "lucide-react";

// ─── Types ──────────────────────────────────────────────────

interface ParamDoc {
  name: string;
  type: string;
  required: boolean;
  default?: string;
  description: string;
}

interface ApiEndpoint {
  id: string;
  method: "GET" | "POST" | "PUT" | "DELETE";
  path: string;
  title: string;
  description: string;
  group: string;
  parameters?: ParamDoc[];
  requestBody?: ParamDoc[];
  exampleRequest: string;
  exampleResponse: string;
}

// ─── Method Colors ──────────────────────────────────────────

const METHOD_COLORS: Record<string, string> = {
  GET: "bg-emerald-500/15 text-emerald-400 border-emerald-500/25",
  POST: "bg-blue-500/15 text-blue-400 border-blue-500/25",
  PUT: "bg-amber-500/15 text-amber-400 border-amber-500/25",
  DELETE: "bg-red-500/15 text-red-400 border-red-500/25",
};

// ─── API Documentation Data ─────────────────────────────────

const INTRO_SECTIONS = [
  { id: "overview", title: "Overview" },
  { id: "authentication", title: "Authentication" },
  { id: "errors", title: "Errors" },
];

const ENDPOINTS: ApiEndpoint[] = [
  // ── Tax Calculation ──
  {
    id: "post-tax-calculate",
    method: "POST",
    path: "/v1/tax/calculate",
    title: "Calculate Tax",
    description:
      "Calculate all applicable accommodation taxes for a specific stay. The engine traverses the jurisdiction hierarchy (country → state → city), collects all active rates, evaluates rules (exemptions, reductions, caps, surcharges), and returns an itemized breakdown. Supports flat, percentage, and tiered rate types with per-stay and per-night charging models.",
    group: "Tax Calculation",
    requestBody: [
      { name: "jurisdiction_code", type: "string", required: true, description: "ISO jurisdiction code (e.g. \"US-NY-NYC\", \"HR-19-DBV\")" },
      { name: "stay_date", type: "date", required: true, description: "Check-in date (YYYY-MM-DD)" },
      { name: "checkout_date", type: "date", required: false, description: "Check-out date. Optional — nights is the authoritative duration." },
      { name: "nightly_rate", type: "decimal", required: true, description: "Room rate per night. Must be > 0." },
      { name: "currency", type: "string", required: true, description: "ISO 4217 currency code (e.g. \"USD\", \"EUR\", \"JPY\")" },
      { name: "nights", type: "integer", required: true, description: "Number of nights (>= 1)" },
      { name: "number_of_guests", type: "integer", required: false, default: "1", description: "Guest count. Affects per-person taxes." },
      { name: "property_type", type: "string", required: false, default: "\"hotel\"", description: "Property classification: hotel, short_term_rental, hostel, etc." },
      { name: "star_rating", type: "integer", required: false, description: "Hotel star rating (1-5). Used for tiered rates (e.g. Florence, Milan)." },
      { name: "guest_type", type: "string", required: false, default: "\"standard\"", description: "Guest classification: standard, business, government, etc." },
      { name: "guest_age", type: "integer", required: false, description: "Guest age. Triggers age-based exemptions/reductions (e.g. Croatia: under 12 exempt, 12-17 half price)." },
      { name: "guest_nationality", type: "string", required: false, description: "ISO country code. Triggers nationality-based rules (e.g. Bhutan: SAARC countries exempt)." },
      { name: "is_marketplace", type: "boolean", required: false, default: "false", description: "Whether booked through an OTA marketplace. Triggers platform surcharges (e.g. Denver +2%)." },
      { name: "platform_type", type: "string", required: false, default: "\"direct\"", description: "Booking channel: direct, ota, metasearch, etc." },
      { name: "is_bundled", type: "boolean", required: false, default: "false", description: "Whether the room is part of a bundled package." },
    ],
    exampleRequest: `curl -X POST https://api.taxlens.getdynamiq.ai/v1/tax/calculate \\
  -H "Content-Type: application/json" \\
  -H "X-API-Key: dev-api-key-change-me" \\
  -d '{
    "jurisdiction_code": "US-NY-NYC",
    "stay_date": "2025-06-15",
    "nightly_rate": 250,
    "currency": "USD",
    "nights": 3,
    "number_of_guests": 2
  }'`,
    exampleResponse: `{
  "calculation_id": "f8cbd38c-bbf1-4e19-af08-d22510759877",
  "jurisdiction": {
    "code": "US-NY-NYC",
    "name": "New York City",
    "path": "US.NY.NYC"
  },
  "input": {
    "nightly_rate": 250.0,
    "nights": 3,
    "subtotal": 750.0,
    "currency": "USD",
    "property_type": "hotel"
  },
  "tax_breakdown": {
    "components": [
      {
        "name": "VAT / Sales Tax (standard)",
        "category_code": "vat_standard",
        "jurisdiction_code": "US-NY",
        "jurisdiction_level": "state",
        "rate": 0.04,
        "rate_type": "percentage",
        "taxable_amount": "750",
        "tax_amount": "30.00",
        "legal_reference": "NY Tax Law §1105(e)",
        "authority": "New York State Dept. of Taxation"
      },
      {
        "name": "Occupancy Tax (% of room)",
        "category_code": "occ_pct",
        "jurisdiction_code": "US-NY-NYC",
        "jurisdiction_level": "city",
        "rate": 0.05875,
        "rate_type": "percentage",
        "taxable_amount": "750",
        "tax_amount": "44.06",
        "legal_reference": "NYC Admin Code §11-2502",
        "authority": "NYC Department of Finance"
      }
    ],
    "total_tax": "113.81",
    "effective_rate": "0.15",
    "currency": "USD"
  },
  "total_with_tax": "863.81",
  "rules_applied": [
    {
      "rule_id": 1,
      "name": "Permanent Resident Exemption (180+ days)",
      "rule_type": "exemption",
      "result": "skipped"
    }
  ],
  "calculated_at": "2026-03-12T10:29:52.943980Z",
  "data_version": null
}`,
  },
  {
    id: "post-tax-batch",
    method: "POST",
    path: "/v1/tax/calculate/batch",
    title: "Batch Calculate",
    description:
      "Calculate taxes for multiple stays in a single request. Each item in the batch is calculated independently. Useful for comparing rates across jurisdictions or processing bulk bookings.",
    group: "Tax Calculation",
    requestBody: [
      { name: "calculations", type: "array", required: true, description: "Array of TaxCalculationRequest objects (same schema as single calculate endpoint)." },
    ],
    exampleRequest: `curl -X POST https://api.taxlens.getdynamiq.ai/v1/tax/calculate/batch \\
  -H "Content-Type: application/json" \\
  -H "X-API-Key: dev-api-key-change-me" \\
  -d '{
    "calculations": [
      {
        "jurisdiction_code": "US-NY-NYC",
        "stay_date": "2025-06-15",
        "nightly_rate": 200, "currency": "USD",
        "nights": 2
      },
      {
        "jurisdiction_code": "HR-19-DBV",
        "stay_date": "2025-07-01",
        "nightly_rate": 150, "currency": "EUR",
        "nights": 5, "guest_age": 15
      }
    ]
  }'`,
    exampleResponse: `{
  "results": [
    {
      "id": null,
      "total_tax": "75.88",
      "effective_rate": "0.19",
      "components": [...],
      "error": null
    },
    {
      "id": null,
      "total_tax": "4.65",
      "effective_rate": "0.01",
      "components": [...],
      "error": null
    }
  ]
}`,
  },

  // ── Jurisdictions ──
  {
    id: "get-jurisdictions",
    method: "GET",
    path: "/v1/jurisdictions",
    title: "List Jurisdictions",
    description:
      "Retrieve a paginated list of jurisdictions. Supports filtering by country, type, status, and parent. Use this to discover available jurisdictions in the hierarchy.",
    group: "Jurisdictions",
    parameters: [
      { name: "country_code", type: "string", required: false, description: "Filter by ISO country code (e.g. \"US\", \"HR\")" },
      { name: "jurisdiction_type", type: "string", required: false, description: "Filter by type: country, state, province, region, city, district, special_zone" },
      { name: "status", type: "string", required: false, description: "Filter by status: active, inactive, pending" },
      { name: "parent_code", type: "string", required: false, description: "Filter by parent jurisdiction code" },
      { name: "q", type: "string", required: false, description: "Search by name or code (case-insensitive)" },
      { name: "limit", type: "integer", required: false, default: "100", description: "Max results (1-500)" },
      { name: "offset", type: "integer", required: false, default: "0", description: "Pagination offset" },
    ],
    exampleRequest: `curl https://api.taxlens.getdynamiq.ai/v1/jurisdictions?country_code=US&jurisdiction_type=state \\
  -H "X-API-Key: dev-api-key-change-me"`,
    exampleResponse: `[
  {
    "id": 2,
    "code": "US-NY",
    "name": "New York",
    "local_name": null,
    "jurisdiction_type": "state",
    "path": "US.NY",
    "parent_id": 1,
    "country_code": "US",
    "subdivision_code": "US-NY",
    "timezone": "America/New_York",
    "currency_code": "USD",
    "status": "active",
    "created_by": "system",
    "created_at": "2026-03-12T00:52:31.340Z",
    "updated_at": "2026-03-12T00:52:31.340Z"
  },
  ...
]`,
  },
  {
    id: "get-jurisdiction",
    method: "GET",
    path: "/v1/jurisdictions/{code}",
    title: "Get Jurisdiction",
    description: "Retrieve a single jurisdiction by its code.",
    group: "Jurisdictions",
    parameters: [
      { name: "code", type: "string", required: true, description: "Jurisdiction code (path parameter)" },
    ],
    exampleRequest: `curl https://api.taxlens.getdynamiq.ai/v1/jurisdictions/US-NY-NYC \\
  -H "X-API-Key: dev-api-key-change-me"`,
    exampleResponse: `{
  "id": 3,
  "code": "US-NY-NYC",
  "name": "New York City",
  "jurisdiction_type": "city",
  "path": "US.NY.NYC",
  "parent_id": 2,
  "country_code": "US",
  "subdivision_code": "US-NY",
  "timezone": "America/New_York",
  "currency_code": "USD",
  "status": "active"
}`,
  },
  {
    id: "get-jurisdiction-children",
    method: "GET",
    path: "/v1/jurisdictions/{code}/children",
    title: "Get Children",
    description:
      "Retrieve direct child jurisdictions. Use this for progressive disclosure — start from a country and drill down through states/regions to cities.",
    group: "Jurisdictions",
    parameters: [
      { name: "code", type: "string", required: true, description: "Parent jurisdiction code (path parameter)" },
    ],
    exampleRequest: `curl https://api.taxlens.getdynamiq.ai/v1/jurisdictions/US/children \\
  -H "X-API-Key: dev-api-key-change-me"`,
    exampleResponse: `[
  { "code": "US-CA", "name": "California", "jurisdiction_type": "state", ... },
  { "code": "US-CO", "name": "Colorado", "jurisdiction_type": "state", ... },
  { "code": "US-NY", "name": "New York", "jurisdiction_type": "state", ... },
  ...
]`,
  },
  {
    id: "get-jurisdiction-ancestors",
    method: "GET",
    path: "/v1/jurisdictions/{code}/ancestors",
    title: "Get Ancestors",
    description:
      "Retrieve the full ancestor chain from root to the parent of the given jurisdiction. Useful for building breadcrumb trails. The jurisdiction itself is NOT included.",
    group: "Jurisdictions",
    parameters: [
      { name: "code", type: "string", required: true, description: "Jurisdiction code (path parameter)" },
    ],
    exampleRequest: `curl https://api.taxlens.getdynamiq.ai/v1/jurisdictions/US-NY-NYC/ancestors \\
  -H "X-API-Key: dev-api-key-change-me"`,
    exampleResponse: `[
  { "code": "US", "name": "United States", "jurisdiction_type": "country", ... },
  { "code": "US-NY", "name": "New York", "jurisdiction_type": "state", ... }
]`,
  },
  {
    id: "post-jurisdiction",
    method: "POST",
    path: "/v1/jurisdictions",
    title: "Create Jurisdiction",
    description: "Create a new jurisdiction. If parent_code is provided, the new jurisdiction is linked as a child.",
    group: "Jurisdictions",
    requestBody: [
      { name: "code", type: "string", required: true, description: "Unique jurisdiction code (e.g. \"US-NY-NYC\")" },
      { name: "name", type: "string", required: true, description: "Display name" },
      { name: "local_name", type: "string", required: false, description: "Name in local language" },
      { name: "jurisdiction_type", type: "string", required: true, description: "country, state, province, region, city, district, special_zone" },
      { name: "parent_code", type: "string", required: false, description: "Parent jurisdiction code" },
      { name: "country_code", type: "string", required: true, description: "ISO 2-letter country code" },
      { name: "subdivision_code", type: "string", required: false, description: "ISO 3166-2 subdivision code" },
      { name: "timezone", type: "string", required: false, description: "IANA timezone (e.g. \"America/New_York\")" },
      { name: "currency_code", type: "string", required: true, description: "ISO 4217 currency code" },
      { name: "status", type: "string", required: false, default: "\"active\"", description: "active, inactive, pending" },
      { name: "metadata", type: "object", required: false, default: "{}", description: "Arbitrary key-value metadata" },
    ],
    exampleRequest: `curl -X POST https://api.taxlens.getdynamiq.ai/v1/jurisdictions \\
  -H "Content-Type: application/json" \\
  -H "X-API-Key: dev-api-key-change-me" \\
  -d '{
    "code": "US-WA-SEA",
    "name": "Seattle",
    "jurisdiction_type": "city",
    "parent_code": "US-WA",
    "country_code": "US",
    "currency_code": "USD",
    "timezone": "America/Los_Angeles"
  }'`,
    exampleResponse: `{
  "id": 103,
  "code": "US-WA-SEA",
  "name": "Seattle",
  "jurisdiction_type": "city",
  "path": "US.WA.SEA",
  "parent_id": 42,
  "country_code": "US",
  "currency_code": "USD",
  "status": "active",
  ...
}`,
  },

  // ── Tax Rates ──
  {
    id: "get-rates",
    method: "GET",
    path: "/v1/rates",
    title: "List Rates",
    description: "Retrieve a paginated list of tax rates. Rates define the actual tax amounts: percentage, flat, or tiered.",
    group: "Tax Rates",
    parameters: [
      { name: "jurisdiction_code", type: "string", required: false, description: "Filter by jurisdiction code" },
      { name: "category_code", type: "string", required: false, description: "Filter by tax category code" },
      { name: "status", type: "string", required: false, description: "Filter: active, draft, approved, scheduled, superseded, rejected, needs_review" },
      { name: "effective_date", type: "date", required: false, description: "Filter rates effective on this date" },
      { name: "limit", type: "integer", required: false, default: "100", description: "Max results (1-500)" },
      { name: "offset", type: "integer", required: false, default: "0", description: "Pagination offset" },
    ],
    exampleRequest: `curl "https://api.taxlens.getdynamiq.ai/v1/rates?jurisdiction_code=US-NY-NYC&status=active" \\
  -H "X-API-Key: dev-api-key-change-me"`,
    exampleResponse: `[
  {
    "id": 3,
    "jurisdiction_code": "US-NY-NYC",
    "tax_category_code": "occ_pct",
    "rate_type": "percentage",
    "rate_value": 0.05875,
    "currency_code": "USD",
    "calculation_order": 30,
    "effective_start": "2024-01-01",
    "status": "active",
    "legal_reference": "NYC Admin Code §11-2502",
    ...
  }
]`,
  },
  {
    id: "get-rates-lookup",
    method: "GET",
    path: "/v1/rates/lookup",
    title: "Lookup Rates",
    description:
      "Look up all active rates for a jurisdiction on a given date, including inherited rates from parent jurisdictions. Returns the combined percentage rate — useful for displaying the total tax rate to users before they book.",
    group: "Tax Rates",
    parameters: [
      { name: "jurisdiction_code", type: "string", required: true, description: "Jurisdiction code to look up" },
      { name: "effective_date", type: "date", required: false, description: "Date to check (defaults to today)" },
    ],
    exampleRequest: `curl "https://api.taxlens.getdynamiq.ai/v1/rates/lookup?jurisdiction_code=US-NY-NYC" \\
  -H "X-API-Key: dev-api-key-change-me"`,
    exampleResponse: `{
  "jurisdiction": {
    "code": "US-NY-NYC",
    "name": "New York City",
    "path": "US.NY.NYC"
  },
  "date": "2026-03-12",
  "rates": [
    {
      "jurisdiction_code": "US-NY",
      "tax_category_code": "vat_standard",
      "rate_type": "percentage",
      "rate_value": 0.04,
      ...
    },
    {
      "jurisdiction_code": "US-NY-NYC",
      "tax_category_code": "occ_pct",
      "rate_type": "percentage",
      "rate_value": 0.05875,
      ...
    }
  ],
  "combined_percentage_rate": 0.14375
}`,
  },
  {
    id: "get-rate",
    method: "GET",
    path: "/v1/rates/{rate_id}",
    title: "Get Rate",
    description: "Retrieve a single tax rate by ID.",
    group: "Tax Rates",
    parameters: [
      { name: "rate_id", type: "integer", required: true, description: "Rate ID (path parameter)" },
    ],
    exampleRequest: `curl https://api.taxlens.getdynamiq.ai/v1/rates/3 \\
  -H "X-API-Key: dev-api-key-change-me"`,
    exampleResponse: `{
  "id": 3,
  "jurisdiction_code": "US-NY-NYC",
  "tax_category_code": "occ_pct",
  "rate_type": "percentage",
  "rate_value": 0.05875,
  "currency_code": "USD",
  "tiers": null,
  "calculation_order": 30,
  "base_includes": ["base_amount"],
  "effective_start": "2024-01-01",
  "effective_end": null,
  "status": "active",
  "legal_reference": "NYC Admin Code §11-2502",
  "authority_name": "NYC Department of Finance",
  ...
}`,
  },
  {
    id: "post-rate",
    method: "POST",
    path: "/v1/rates",
    title: "Create Rate",
    description: "Create a new tax rate for a jurisdiction.",
    group: "Tax Rates",
    requestBody: [
      { name: "jurisdiction_code", type: "string", required: true, description: "Jurisdiction code" },
      { name: "tax_category_code", type: "string", required: true, description: "Tax category code" },
      { name: "rate_type", type: "string", required: true, description: "percentage, flat, or tiered" },
      { name: "rate_value", type: "float", required: false, description: "Rate value. Required for percentage (0.05 = 5%) and flat types." },
      { name: "currency_code", type: "string", required: false, description: "Currency code (required for flat rates)" },
      { name: "tiers", type: "array", required: false, description: "Tier definitions. Required for tiered type." },
      { name: "tier_type", type: "string", required: false, description: "single_amount, threshold, or marginal_rate" },
      { name: "effective_start", type: "date", required: true, description: "Date the rate becomes effective" },
      { name: "effective_end", type: "date", required: false, description: "Date the rate expires" },
      { name: "calculation_order", type: "integer", required: false, default: "100", description: "Order of calculation when multiple rates apply" },
      { name: "base_includes", type: "array", required: false, default: "[\"base_amount\"]", description: "What amounts are included in the tax base. Use for anti-compounding." },
      { name: "legal_reference", type: "string", required: false, description: "Legal citation" },
      { name: "source_url", type: "string", required: false, description: "URL to authoritative source" },
      { name: "authority_name", type: "string", required: false, description: "Name of issuing authority" },
      { name: "status", type: "string", required: false, default: "\"active\"", description: "Rate status" },
    ],
    exampleRequest: `curl -X POST https://api.taxlens.getdynamiq.ai/v1/rates \\
  -H "Content-Type: application/json" \\
  -H "X-API-Key: dev-api-key-change-me" \\
  -d '{
    "jurisdiction_code": "US-NY-NYC",
    "tax_category_code": "occ_pct",
    "rate_type": "percentage",
    "rate_value": 0.06,
    "effective_start": "2026-01-01",
    "legal_reference": "NYC Council Resolution 2025-42"
  }'`,
    exampleResponse: `{
  "id": 100,
  "jurisdiction_code": "US-NY-NYC",
  "tax_category_code": "occ_pct",
  "rate_type": "percentage",
  "rate_value": 0.06,
  "status": "active",
  "effective_start": "2026-01-01",
  ...
}`,
  },
  {
    id: "post-rate-approve",
    method: "POST",
    path: "/v1/rates/{rate_id}/approve",
    title: "Approve Rate",
    description: "Approve a tax rate after review. Changes status to \"approved\".",
    group: "Tax Rates",
    parameters: [
      { name: "rate_id", type: "integer", required: true, description: "Rate ID (path parameter)" },
      { name: "reviewed_by", type: "string", required: false, default: "\"system\"", description: "Reviewer identifier" },
      { name: "review_notes", type: "string", required: false, description: "Review notes" },
    ],
    exampleRequest: `curl -X POST "https://api.taxlens.getdynamiq.ai/v1/rates/5/approve?reviewed_by=alice" \\
  -H "X-API-Key: dev-api-key-change-me"`,
    exampleResponse: `{
  "id": 5,
  "status": "approved",
  "reviewed_by": "alice",
  "reviewed_at": "2026-03-12T10:30:00Z",
  ...
}`,
  },
  {
    id: "post-rate-reject",
    method: "POST",
    path: "/v1/rates/{rate_id}/reject",
    title: "Reject Rate",
    description: "Reject a tax rate. Changes status to \"rejected\".",
    group: "Tax Rates",
    parameters: [
      { name: "rate_id", type: "integer", required: true, description: "Rate ID (path parameter)" },
      { name: "reviewed_by", type: "string", required: false, default: "\"system\"", description: "Reviewer identifier" },
      { name: "review_notes", type: "string", required: false, description: "Reason for rejection" },
    ],
    exampleRequest: `curl -X POST "https://api.taxlens.getdynamiq.ai/v1/rates/5/reject?reviewed_by=alice&review_notes=Outdated" \\
  -H "X-API-Key: dev-api-key-change-me"`,
    exampleResponse: `{
  "id": 5,
  "status": "rejected",
  "reviewed_by": "alice",
  "review_notes": "Outdated",
  ...
}`,
  },

  // ── Tax Rules ──
  {
    id: "get-rules",
    method: "GET",
    path: "/v1/rules",
    title: "List Rules",
    description:
      "Retrieve tax rules. Rules modify how rates are applied: exemptions (zero out tax), reductions (percentage discount), caps (max nights/amount), surcharges (additional %), and overrides.",
    group: "Tax Rules",
    parameters: [
      { name: "jurisdiction_code", type: "string", required: false, description: "Filter by jurisdiction code" },
      { name: "rule_type", type: "string", required: false, description: "Filter: exemption, reduction, surcharge, cap, override, condition, threshold" },
      { name: "status", type: "string", required: false, description: "Filter by status" },
      { name: "tax_rate_id", type: "integer", required: false, description: "Filter by associated rate ID" },
      { name: "limit", type: "integer", required: false, default: "100", description: "Max results (1-500)" },
      { name: "offset", type: "integer", required: false, default: "0", description: "Pagination offset" },
    ],
    exampleRequest: `curl "https://api.taxlens.getdynamiq.ai/v1/rules?jurisdiction_code=HR-19-DBV" \\
  -H "X-API-Key: dev-api-key-change-me"`,
    exampleResponse: `[
  {
    "id": 21,
    "jurisdiction_code": "HR-19-DBV",
    "rule_type": "exemption",
    "priority": 100,
    "name": "Children Under 12 Exemption",
    "conditions": {
      "operator": "AND",
      "conditions": [
        { "field": "guest_age", "op": "<", "value": 12 }
      ]
    },
    "action": { "exempt": true },
    "effective_start": "2025-04-01",
    "status": "active"
  },
  {
    "id": 22,
    "jurisdiction_code": "HR-19-DBV",
    "rule_type": "reduction",
    "priority": 90,
    "name": "Youth 50% Reduction (Ages 12-17)",
    "conditions": {
      "operator": "AND",
      "conditions": [
        { "field": "guest_age", "op": ">=", "value": 12 },
        { "field": "guest_age", "op": "<=", "value": 17 }
      ]
    },
    "action": { "reduction_percent": 0.5 },
    "effective_start": "2025-04-01",
    "status": "active"
  }
]`,
  },
  {
    id: "get-rule",
    method: "GET",
    path: "/v1/rules/{rule_id}",
    title: "Get Rule",
    description: "Retrieve a single tax rule by ID.",
    group: "Tax Rules",
    parameters: [
      { name: "rule_id", type: "integer", required: true, description: "Rule ID (path parameter)" },
    ],
    exampleRequest: `curl https://api.taxlens.getdynamiq.ai/v1/rules/21 \\
  -H "X-API-Key: dev-api-key-change-me"`,
    exampleResponse: `{
  "id": 21,
  "jurisdiction_code": "HR-19-DBV",
  "rule_type": "exemption",
  "priority": 100,
  "name": "Children Under 12 Exemption",
  "conditions": { ... },
  "action": { "exempt": true },
  ...
}`,
  },
  {
    id: "post-rule",
    method: "POST",
    path: "/v1/rules",
    title: "Create Rule",
    description: "Create a new tax rule for a jurisdiction.",
    group: "Tax Rules",
    requestBody: [
      { name: "jurisdiction_code", type: "string", required: true, description: "Jurisdiction code" },
      { name: "rule_type", type: "string", required: true, description: "exemption, reduction, surcharge, cap, override, condition, threshold" },
      { name: "name", type: "string", required: true, description: "Human-readable rule name" },
      { name: "description", type: "string", required: false, description: "Detailed description" },
      { name: "priority", type: "integer", required: false, default: "0", description: "Higher priority rules are evaluated first" },
      { name: "tax_rate_id", type: "integer", required: false, description: "Associated rate ID (if rule applies to specific rate)" },
      { name: "conditions", type: "object", required: false, default: "{}", description: "JSON condition tree with operator (AND/OR) and conditions array" },
      { name: "action", type: "object", required: false, default: "{}", description: "Action payload: { exempt: true }, { reduction_percent: 0.5 }, { max_nights: 28 }, etc." },
      { name: "effective_start", type: "date", required: true, description: "When the rule becomes effective" },
      { name: "effective_end", type: "date", required: false, description: "When the rule expires" },
      { name: "legal_reference", type: "string", required: false, description: "Legal citation" },
      { name: "status", type: "string", required: false, default: "\"active\"", description: "Rule status" },
    ],
    exampleRequest: `curl -X POST https://api.taxlens.getdynamiq.ai/v1/rules \\
  -H "Content-Type: application/json" \\
  -H "X-API-Key: dev-api-key-change-me" \\
  -d '{
    "jurisdiction_code": "US-NY-NYC",
    "rule_type": "exemption",
    "name": "Government Employee Exemption",
    "priority": 100,
    "conditions": {
      "operator": "AND",
      "conditions": [
        { "field": "guest_type", "op": "==", "value": "government" }
      ]
    },
    "action": { "exempt": true },
    "effective_start": "2025-01-01"
  }'`,
    exampleResponse: `{
  "id": 50,
  "jurisdiction_code": "US-NY-NYC",
  "rule_type": "exemption",
  "name": "Government Employee Exemption",
  "status": "active",
  ...
}`,
  },

  // ── Monitoring Sources ──
  {
    id: "get-sources",
    method: "GET",
    path: "/v1/monitoring/sources",
    title: "List Sources",
    description: "List monitored legislative sources. TaxLens tracks government websites, tax authority portals, and legal gazettes for tax changes.",
    group: "Monitoring",
    parameters: [
      { name: "jurisdiction_code", type: "string", required: false, description: "Filter by jurisdiction code" },
      { name: "status", type: "string", required: false, description: "Filter by status" },
      { name: "limit", type: "integer", required: false, default: "100", description: "Max results (1-500)" },
      { name: "offset", type: "integer", required: false, default: "0", description: "Pagination offset" },
    ],
    exampleRequest: `curl "https://api.taxlens.getdynamiq.ai/v1/monitoring/sources?jurisdiction_code=US-NY-NYC" \\
  -H "X-API-Key: dev-api-key-change-me"`,
    exampleResponse: `[
  {
    "id": 1,
    "jurisdiction_code": "US-NY-NYC",
    "url": "https://www.nyc.gov/site/finance/taxes/...",
    "source_type": "government_website",
    "language": "en",
    "check_frequency_days": 7,
    "last_checked_at": "2026-03-10T08:00:00Z",
    "status": "active"
  }
]`,
  },
  {
    id: "post-source",
    method: "POST",
    path: "/v1/monitoring/sources",
    title: "Create Source",
    description: "Register a new legislative source to monitor for changes.",
    group: "Monitoring",
    requestBody: [
      { name: "jurisdiction_code", type: "string", required: false, description: "Jurisdiction this source covers" },
      { name: "url", type: "string", required: true, description: "Source URL to monitor" },
      { name: "source_type", type: "string", required: true, description: "government_website, tax_authority, legal_gazette, regulatory_body" },
      { name: "language", type: "string", required: false, default: "\"en\"", description: "Content language" },
      { name: "check_frequency_days", type: "integer", required: false, default: "7", description: "How often to check (days)" },
    ],
    exampleRequest: `curl -X POST https://api.taxlens.getdynamiq.ai/v1/monitoring/sources \\
  -H "Content-Type: application/json" \\
  -H "X-API-Key: dev-api-key-change-me" \\
  -d '{
    "jurisdiction_code": "US-NY-NYC",
    "url": "https://www.nyc.gov/site/finance/taxes/...",
    "source_type": "government_website"
  }'`,
    exampleResponse: `{
  "id": 50,
  "jurisdiction_code": "US-NY-NYC",
  "url": "https://www.nyc.gov/site/finance/taxes/...",
  "source_type": "government_website",
  "status": "active",
  ...
}`,
  },

  // ── Detected Changes ──
  {
    id: "get-changes",
    method: "GET",
    path: "/v1/monitoring/changes",
    title: "List Changes",
    description: "List detected tax changes from monitored sources. Changes go through a review workflow: needs_review → approved/rejected.",
    group: "Monitoring",
    parameters: [
      { name: "jurisdiction_code", type: "string", required: false, description: "Filter by jurisdiction code" },
      { name: "review_status", type: "string", required: false, description: "Filter: needs_review, approved, rejected" },
      { name: "limit", type: "integer", required: false, default: "100", description: "Max results (1-500)" },
      { name: "offset", type: "integer", required: false, default: "0", description: "Pagination offset" },
    ],
    exampleRequest: `curl "https://api.taxlens.getdynamiq.ai/v1/monitoring/changes?review_status=needs_review" \\
  -H "X-API-Key: dev-api-key-change-me"`,
    exampleResponse: `[
  {
    "id": 1,
    "jurisdiction_code": "US-NY-NYC",
    "change_type": "rate_change",
    "confidence": 0.92,
    "extracted_data": {
      "new_rate": 0.06,
      "old_rate": 0.05875,
      "effective_date": "2026-07-01"
    },
    "source_quote": "The occupancy tax rate...",
    "review_status": "needs_review"
  }
]`,
  },
  {
    id: "post-change-review",
    method: "POST",
    path: "/v1/monitoring/changes/{change_id}/review",
    title: "Review Change",
    description: "Review a detected change — approve, reject, or flag for further review.",
    group: "Monitoring",
    requestBody: [
      { name: "review_status", type: "string", required: true, description: "approved, rejected, or needs_review" },
      { name: "reviewed_by", type: "string", required: false, default: "\"system\"", description: "Reviewer identifier" },
      { name: "review_notes", type: "string", required: false, description: "Review notes" },
    ],
    exampleRequest: `curl -X POST https://api.taxlens.getdynamiq.ai/v1/monitoring/changes/1/review \\
  -H "Content-Type: application/json" \\
  -H "X-API-Key: dev-api-key-change-me" \\
  -d '{
    "review_status": "approved",
    "reviewed_by": "alice",
    "review_notes": "Verified against official gazette"
  }'`,
    exampleResponse: `{
  "id": 1,
  "review_status": "approved",
  "reviewed_by": "alice",
  "reviewed_at": "2026-03-12T11:00:00Z",
  ...
}`,
  },

  // ── Monitoring Jobs ──
  {
    id: "post-monitoring-run",
    method: "POST",
    path: "/v1/monitoring/jobs/{jurisdiction_code}/run",
    title: "Trigger Monitoring Run",
    description: "Start an AI-powered tax monitoring job for a jurisdiction. The agent uses web search to find current tax regulations, compares them against stored data, and creates draft changes for review. Returns 202 Accepted with the job object — poll GET /jobs/{id} for progress.",
    group: "Monitoring Jobs",
    exampleRequest: `curl -X POST https://api.taxlens.getdynamiq.ai/v1/monitoring/jobs/US-NY-NYC/run \\
  -H "X-API-Key: dev-api-key-change-me"`,
    exampleResponse: `{
  "id": 1,
  "jurisdiction_code": "US-NY-NYC",
  "job_type": "monitoring",
  "status": "pending",
  "trigger_type": "manual",
  "triggered_by": "api",
  "started_at": null,
  "completed_at": null,
  "result_summary": null,
  "changes_detected": 0,
  "error_message": null,
  "created_at": "2026-03-26T10:00:00Z"
}`,
  },
  {
    id: "get-monitoring-jobs",
    method: "GET",
    path: "/v1/monitoring/jobs",
    title: "List Monitoring Jobs",
    description: "List monitoring and discovery jobs with optional filters. Use job_type to separate monitoring runs from discovery runs.",
    group: "Monitoring Jobs",
    parameters: [
      { name: "jurisdiction_code", type: "string", required: false, description: "Filter by jurisdiction" },
      { name: "job_type", type: "string", required: false, description: "Filter: monitoring or discovery" },
      { name: "status", type: "string", required: false, description: "Filter: pending, running, completed, failed" },
      { name: "trigger_type", type: "string", required: false, description: "Filter: manual or scheduled" },
      { name: "limit", type: "integer", required: false, default: "100", description: "Max results (1-500)" },
      { name: "offset", type: "integer", required: false, default: "0", description: "Pagination offset" },
    ],
    exampleRequest: `curl "https://api.taxlens.getdynamiq.ai/v1/monitoring/jobs?jurisdiction_code=US-NY-NYC&job_type=monitoring&limit=10" \\
  -H "X-API-Key: dev-api-key-change-me"`,
    exampleResponse: `[
  {
    "id": 1,
    "jurisdiction_code": "US-NY-NYC",
    "job_type": "monitoring",
    "status": "completed",
    "trigger_type": "manual",
    "started_at": "2026-03-26T10:00:05Z",
    "completed_at": "2026-03-26T10:01:30Z",
    "result_summary": {
      "changes_detected": 7,
      "rates_created": 2,
      "rules_created": 5,
      "sources_checked": 8,
      "overall_confidence": 0.88,
      "summary": "Found 7 changes for NYC..."
    },
    "changes_detected": 7
  }
]`,
  },
  {
    id: "get-monitoring-job",
    method: "GET",
    path: "/v1/monitoring/jobs/{job_id}",
    title: "Get Job Details",
    description: "Get a specific monitoring or discovery job. Poll this endpoint to track job progress after triggering a run.",
    group: "Monitoring Jobs",
    exampleRequest: `curl "https://api.taxlens.getdynamiq.ai/v1/monitoring/jobs/1" \\
  -H "X-API-Key: dev-api-key-change-me"`,
    exampleResponse: `{
  "id": 1,
  "jurisdiction_code": "US-NY-NYC",
  "job_type": "monitoring",
  "status": "running",
  "trigger_type": "manual",
  "triggered_by": "api",
  "started_at": "2026-03-26T10:00:05Z",
  "completed_at": null,
  "result_summary": null,
  "changes_detected": 0,
  "error_message": null,
  "created_at": "2026-03-26T10:00:00Z"
}`,
  },

  // ── Monitoring Schedules ──
  {
    id: "get-schedules",
    method: "GET",
    path: "/v1/monitoring/schedules",
    title: "List Schedules",
    description: "List all monitoring schedules. Each jurisdiction can have one schedule that triggers automated monitoring runs on a cron cadence.",
    group: "Schedules",
    parameters: [
      { name: "enabled", type: "boolean", required: false, description: "Filter by enabled status" },
      { name: "limit", type: "integer", required: false, default: "100", description: "Max results (1-500)" },
      { name: "offset", type: "integer", required: false, default: "0", description: "Pagination offset" },
    ],
    exampleRequest: `curl "https://api.taxlens.getdynamiq.ai/v1/monitoring/schedules?enabled=true" \\
  -H "X-API-Key: dev-api-key-change-me"`,
    exampleResponse: `[
  {
    "id": 1,
    "jurisdiction_code": "US-NY-NYC",
    "enabled": true,
    "cadence": "weekly",
    "cron_expression": null,
    "last_run_at": "2026-03-24T03:00:00Z",
    "next_run_at": "2026-03-31T03:00:00Z"
  }
]`,
  },
  {
    id: "get-schedule",
    method: "GET",
    path: "/v1/monitoring/schedules/{jurisdiction_code}",
    title: "Get Schedule",
    description: "Get the monitoring schedule for a specific jurisdiction.",
    group: "Schedules",
    exampleRequest: `curl "https://api.taxlens.getdynamiq.ai/v1/monitoring/schedules/US-NY-NYC" \\
  -H "X-API-Key: dev-api-key-change-me"`,
    exampleResponse: `{
  "id": 1,
  "jurisdiction_code": "US-NY-NYC",
  "enabled": true,
  "cadence": "weekly",
  "cron_expression": null,
  "last_run_at": "2026-03-24T03:00:00Z",
  "next_run_at": "2026-03-31T03:00:00Z"
}`,
  },
  {
    id: "put-schedule",
    method: "PUT",
    path: "/v1/monitoring/schedules/{jurisdiction_code}",
    title: "Update Schedule",
    description: "Create or update a monitoring schedule. Supports daily, weekly, monthly, or custom cron cadences. Set enabled=true to activate automated monitoring.",
    group: "Schedules",
    requestBody: [
      { name: "enabled", type: "boolean", required: false, description: "Enable or disable the schedule" },
      { name: "cadence", type: "string", required: false, description: "Cadence: daily, weekly, monthly, or custom" },
      { name: "cron_expression", type: "string", required: false, description: "Custom cron expression (required when cadence is 'custom'). Example: '0 3 * * 1' for Monday 3 AM" },
    ],
    exampleRequest: `curl -X PUT https://api.taxlens.getdynamiq.ai/v1/monitoring/schedules/US-NY-NYC \\
  -H "Content-Type: application/json" \\
  -H "X-API-Key: dev-api-key-change-me" \\
  -d '{
    "enabled": true,
    "cadence": "weekly"
  }'`,
    exampleResponse: `{
  "id": 1,
  "jurisdiction_code": "US-NY-NYC",
  "enabled": true,
  "cadence": "weekly",
  "cron_expression": null,
  "next_run_at": "2026-03-31T03:00:00Z"
}`,
  },

  // ── Discovery ──
  {
    id: "post-discovery-run",
    method: "POST",
    path: "/v1/monitoring/discovery/{country_code}/run",
    title: "Trigger Discovery",
    description: "Start an AI-powered sub-jurisdiction discovery for a country. The agent searches official sources to find all states, cities, and districts that levy their own accommodation taxes. Creates new jurisdictions with status='pending' and initial draft tax rates. Only works on country-level jurisdictions.",
    group: "Discovery",
    exampleRequest: `curl -X POST https://api.taxlens.getdynamiq.ai/v1/monitoring/discovery/AE/run \\
  -H "X-API-Key: dev-api-key-change-me"`,
    exampleResponse: `{
  "id": 1,
  "jurisdiction_code": "AE",
  "job_type": "discovery",
  "status": "pending",
  "trigger_type": "manual",
  "triggered_by": "api",
  "started_at": null,
  "completed_at": null,
  "result_summary": null,
  "changes_detected": 0
}`,
  },
  {
    id: "get-discovery-jobs",
    method: "GET",
    path: "/v1/monitoring/discovery/jobs",
    title: "List Discovery Jobs",
    description: "List all jurisdiction discovery jobs.",
    group: "Discovery",
    parameters: [
      { name: "country_code", type: "string", required: false, description: "Filter by country code" },
      { name: "status", type: "string", required: false, description: "Filter: pending, running, completed, failed" },
      { name: "limit", type: "integer", required: false, default: "100", description: "Max results" },
      { name: "offset", type: "integer", required: false, default: "0", description: "Pagination offset" },
    ],
    exampleRequest: `curl "https://api.taxlens.getdynamiq.ai/v1/monitoring/discovery/jobs?country_code=AE" \\
  -H "X-API-Key: dev-api-key-change-me"`,
    exampleResponse: `[
  {
    "id": 1,
    "jurisdiction_code": "AE",
    "job_type": "discovery",
    "status": "completed",
    "result_summary": {
      "jurisdictions_discovered": 2,
      "jurisdictions_created": 2,
      "hierarchy_depth": 1,
      "overall_confidence": 0.92,
      "summary": "Found Abu Dhabi and Ras Al Khaimah..."
    },
    "changes_detected": 2
  }
]`,
  },

  // ── Audit Log ──
  {
    id: "get-audit",
    method: "GET",
    path: "/v1/audit",
    title: "List Audit Log",
    description: "Retrieve audit trail entries. Every create, update, and delete is logged with before/after values, who made the change, and why.",
    group: "Audit",
    parameters: [
      { name: "entity_type", type: "string", required: false, description: "Filter by entity type (e.g. \"tax_rate\", \"jurisdiction\")" },
      { name: "entity_id", type: "integer", required: false, description: "Filter by entity ID" },
      { name: "limit", type: "integer", required: false, default: "100", description: "Max results (1-500)" },
      { name: "offset", type: "integer", required: false, default: "0", description: "Pagination offset" },
    ],
    exampleRequest: `curl "https://api.taxlens.getdynamiq.ai/v1/audit?entity_type=tax_rate&limit=10" \\
  -H "X-API-Key: dev-api-key-change-me"`,
    exampleResponse: `[
  {
    "id": 1,
    "entity_type": "tax_rate",
    "entity_id": 5,
    "action": "update",
    "old_values": { "rate_value": 0.05 },
    "new_values": { "rate_value": 0.06 },
    "changed_by": "alice",
    "change_source": "api",
    "change_reason": "Annual rate adjustment",
    "created_at": "2026-03-12T10:00:00Z"
  }
]`,
  },
];

// ─── Group endpoints ────────────────────────────────────────

const GROUPS = [
  "Tax Calculation",
  "Jurisdictions",
  "Tax Rates",
  "Tax Rules",
  "Monitoring",
  "Monitoring Jobs",
  "Schedules",
  "Discovery",
  "Audit",
];

function groupedEndpoints() {
  return GROUPS.map((group) => ({
    group,
    endpoints: ENDPOINTS.filter((e) => e.group === group),
  }));
}

// ─── Main Component ─────────────────────────────────────────

export default function ApiDocs() {
  const [activeId, setActiveId] = useState("overview");
  const contentRef = useRef<HTMLDivElement>(null);

  // Scroll spy via IntersectionObserver
  useEffect(() => {
    const container = contentRef.current;
    if (!container) return;

    const ids = [...INTRO_SECTIONS.map((s) => s.id), ...ENDPOINTS.map((e) => e.id)];
    const elements = ids
      .map((id) => container.querySelector(`#${id}`))
      .filter(Boolean) as HTMLElement[];

    const observer = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (entry.isIntersecting) {
            setActiveId(entry.target.id);
            break;
          }
        }
      },
      { root: container, rootMargin: "-10% 0px -80% 0px", threshold: 0 }
    );

    for (const el of elements) observer.observe(el);
    return () => observer.disconnect();
  }, []);

  const scrollTo = useCallback((id: string) => {
    const el = contentRef.current?.querySelector(`#${id}`);
    if (el) el.scrollIntoView({ behavior: "smooth", block: "start" });
  }, []);

  const grouped = groupedEndpoints();

  return (
    <PageTransition>
    <div className="flex h-full">
      {/* Sidebar */}
      <aside className="hidden lg:block w-[240px] flex-shrink-0 border-r border-border bg-surface overflow-y-auto">
        <div className="px-5 pt-6 pb-4">
          <h2 className="text-sm font-bold text-text tracking-tight">API Reference</h2>
          <p className="text-xs text-dim mt-1">v1</p>
        </div>

        <nav className="px-3 pb-6">
          {/* Intro sections */}
          <div className="mb-4">
            {INTRO_SECTIONS.map((s) => (
              <SidebarLink
                key={s.id}
                id={s.id}
                label={s.title}
                active={activeId === s.id}
                onClick={scrollTo}
              />
            ))}
          </div>

          {/* Endpoint groups */}
          {grouped.map(({ group, endpoints }) => (
            <div key={group} className="mb-4">
              <div className="px-3 py-1.5 text-[11px] font-bold uppercase tracking-widest text-dim">
                {group}
              </div>
              {endpoints.map((ep) => (
                <SidebarLink
                  key={ep.id}
                  id={ep.id}
                  label={ep.title}
                  method={ep.method}
                  active={activeId === ep.id}
                  onClick={scrollTo}
                />
              ))}
            </div>
          ))}
        </nav>
      </aside>

      {/* Main content */}
      <div ref={contentRef} className="flex-1 overflow-y-auto">
        <div className="max-w-[1000px] mx-auto px-4 sm:px-6 lg:px-10 py-6 lg:py-10">
          {/* Intro sections */}
          <OverviewSection />
          <AuthSection />
          <ErrorsSection />

          {/* Endpoint sections */}
          {grouped.map(({ group, endpoints }) => (
            <div key={group}>
              <h2 className="text-2xl font-bold text-text mt-16 mb-2">{group}</h2>
              <div className="h-px bg-border mb-8" />
              {endpoints.map((ep) => (
                <EndpointSection key={ep.id} endpoint={ep} />
              ))}
            </div>
          ))}

          <div className="h-40" />
        </div>
      </div>
    </div>
    </PageTransition>
  );
}

// ─── Sidebar Link ───────────────────────────────────────────

function SidebarLink({
  id,
  label,
  method,
  active,
  onClick,
}: {
  id: string;
  label: string;
  method?: string;
  active: boolean;
  onClick: (id: string) => void;
}) {
  return (
    <button
      onClick={() => onClick(id)}
      className={cn(
        "w-full flex items-center gap-2 px-3 py-1.5 rounded-md text-left text-sm transition-colors",
        active
          ? "bg-accent/10 text-accent font-medium"
          : "text-muted hover:text-text hover:bg-hover"
      )}
    >
      {method && (
        <span
          className={cn(
            "text-[10px] font-bold uppercase w-9 text-center shrink-0",
            method === "GET" && "text-emerald-400",
            method === "POST" && "text-blue-400",
            method === "PUT" && "text-amber-400",
            method === "DELETE" && "text-red-400"
          )}
        >
          {method}
        </span>
      )}
      <span className="truncate">{label}</span>
    </button>
  );
}

// ─── Intro Sections ─────────────────────────────────────────

function OverviewSection() {
  return (
    <section id="overview" className="mb-16">
      <h1 className="text-3xl font-bold text-text tracking-tight mb-4">
        TaxLens API Reference
      </h1>
      <p className="text-muted text-base leading-relaxed mb-6">
        The TaxLens API provides programmatic access to global accommodation tax data.
        Calculate taxes for any jurisdiction, look up rates, manage rules, and monitor
        legislative changes — all through a single REST API.
      </p>
      <div className="grid grid-cols-2 gap-4">
        <InfoCard label="Base URL" value="https://api.taxlens.getdynamiq.ai" mono />
        <InfoCard label="Content Type" value="application/json" mono />
        <InfoCard label="API Version" value="v1" />
        <InfoCard label="Auth" value="X-API-Key header" />
      </div>
    </section>
  );
}

function AuthSection() {
  return (
    <section id="authentication" className="mb-16">
      <h2 className="text-2xl font-bold text-text mb-4">Authentication</h2>
      <p className="text-muted text-base leading-relaxed mb-4">
        All API requests (except <code className="text-sm font-mono bg-surface px-1.5 py-0.5 rounded border border-border">/health</code>)
        require an API key passed in the <code className="text-sm font-mono bg-surface px-1.5 py-0.5 rounded border border-border">X-API-Key</code> header.
      </p>
      <CodeBlock
        title="Example"
        code={`curl https://api.taxlens.getdynamiq.ai/v1/jurisdictions \\
  -H "X-API-Key: dev-api-key-change-me"`}
      />
      <p className="text-sm text-dim mt-3">
        Requests without a valid key receive a <code className="font-mono">401 Unauthorized</code> response.
      </p>
    </section>
  );
}

function ErrorsSection() {
  return (
    <section id="errors" className="mb-16">
      <h2 className="text-2xl font-bold text-text mb-4">Errors</h2>
      <p className="text-muted text-base leading-relaxed mb-4">
        The API uses standard HTTP status codes. Error responses include a JSON body with a <code className="text-sm font-mono bg-surface px-1.5 py-0.5 rounded border border-border">detail</code> field.
      </p>
      <div className="border border-border rounded-lg overflow-hidden">
        <table className="w-full text-sm">
          <thead>
            <tr className="bg-surface border-b border-border">
              <th className="px-5 py-3 text-left font-semibold text-dim uppercase tracking-wider text-xs">Code</th>
              <th className="px-5 py-3 text-left font-semibold text-dim uppercase tracking-wider text-xs">Meaning</th>
            </tr>
          </thead>
          <tbody>
            {[
              ["200", "Success"],
              ["201", "Created (for POST endpoints)"],
              ["400", "Bad request — invalid parameters"],
              ["401", "Unauthorized — missing or invalid API key"],
              ["404", "Not found — resource does not exist"],
              ["409", "Conflict — resource already exists"],
              ["422", "Validation error — check field constraints"],
              ["500", "Internal server error"],
            ].map(([code, meaning]) => (
              <tr key={code} className="border-b border-border last:border-b-0">
                <td className="px-5 py-3 font-mono font-semibold text-text">{code}</td>
                <td className="px-5 py-3 text-muted">{meaning}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <CodeBlock
        title="Error Response"
        code={`{
  "detail": "Jurisdiction not found: XX-YY-ZZ"
}`}
      />
    </section>
  );
}

// ─── Endpoint Section ───────────────────────────────────────

function EndpointSection({ endpoint }: { endpoint: ApiEndpoint }) {
  const { id, method, path, title, description, parameters, requestBody, exampleRequest, exampleResponse } = endpoint;

  return (
    <section id={id} className="mb-14">
      {/* Header */}
      <div className="flex items-center gap-3 mb-3">
        <MethodBadge method={method} />
        <code className="text-base font-mono font-semibold text-text">{path}</code>
      </div>
      <h3 className="text-xl font-semibold text-text mb-2">{title}</h3>
      <p className="text-muted text-sm leading-relaxed mb-6">{description}</p>

      {/* Two-column: params + examples */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Left: Parameters */}
        <div>
          {parameters && parameters.length > 0 && (
            <ParamsTable title="Parameters" params={parameters} />
          )}
          {requestBody && requestBody.length > 0 && (
            <ParamsTable title="Request Body" params={requestBody} />
          )}
          {!parameters?.length && !requestBody?.length && (
            <div className="text-sm text-dim italic">No parameters</div>
          )}
        </div>

        {/* Right: Examples */}
        <div className="space-y-4">
          <CodeBlock title="Request" code={exampleRequest} />
          <CodeBlock title="Response" code={exampleResponse} />
        </div>
      </div>
    </section>
  );
}

// ─── Method Badge ───────────────────────────────────────────

function MethodBadge({ method }: { method: string }) {
  return (
    <span
      className={cn(
        "inline-flex items-center px-2.5 py-1 rounded-md border text-xs font-bold uppercase tracking-wide",
        METHOD_COLORS[method] || "bg-surface text-muted border-border"
      )}
    >
      {method}
    </span>
  );
}

// ─── Parameters Table ───────────────────────────────────────

function ParamsTable({ title, params }: { title: string; params: ParamDoc[] }) {
  return (
    <div className="mb-6">
      <h4 className="text-xs font-bold uppercase tracking-widest text-dim mb-3">{title}</h4>
      <div className="border border-border rounded-lg divide-y divide-border">
        {params.map((p) => (
          <div key={p.name} className="px-4 py-3">
            <div className="flex items-center gap-2 mb-1">
              <code className="text-sm font-mono font-semibold text-text">{p.name}</code>
              <span className="text-xs text-dim">{p.type}</span>
              {p.required ? (
                <span className="text-[10px] font-bold uppercase text-danger">required</span>
              ) : (
                <span className="text-[10px] font-bold uppercase text-dim">optional</span>
              )}
            </div>
            <p className="text-xs text-muted leading-relaxed">{p.description}</p>
            {p.default && (
              <p className="text-xs text-dim mt-1">
                Default: <code className="font-mono">{p.default}</code>
              </p>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

// ─── Code Block ─────────────────────────────────────────────

function CodeBlock({ title, code }: { title: string; code: string }) {
  const [copied, setCopied] = useState(false);

  const copy = useCallback(() => {
    navigator.clipboard.writeText(code).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  }, [code]);

  return (
    <div className="rounded-lg border border-border overflow-hidden">
      <div className="flex items-center justify-between px-4 py-2 bg-surface border-b border-border">
        <span className="text-xs font-semibold uppercase tracking-widest text-dim">{title}</span>
        <button
          onClick={copy}
          className="flex items-center gap-1 text-xs text-dim hover:text-text transition-colors"
        >
          {copied ? <Check className="w-3.5 h-3.5 text-success" /> : <Copy className="w-3.5 h-3.5" />}
          {copied ? "Copied" : "Copy"}
        </button>
      </div>
      <pre className="px-4 py-4 overflow-x-auto bg-[#0d1117] text-[13px] leading-relaxed">
        <code className="text-[#c9d1d9] font-mono whitespace-pre">{code}</code>
      </pre>
    </div>
  );
}

// ─── Info Card ──────────────────────────────────────────────

function InfoCard({ label, value, mono }: { label: string; value: string; mono?: boolean }) {
  return (
    <div className="border border-border rounded-lg px-5 py-4 bg-card">
      <div className="text-xs font-semibold uppercase tracking-widest text-dim mb-1">{label}</div>
      <div className={cn("text-sm text-text", mono && "font-mono")}>{value}</div>
    </div>
  );
}
