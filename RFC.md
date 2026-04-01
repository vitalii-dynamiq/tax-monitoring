# RFC: Global Accommodation Tax Intelligence Platform (TaxLens)

**Status:** Draft v2
**Authors:** Engineering Team
**Created:** 2026-03-12
**Last Updated:** 2026-03-12

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Problem Statement](#2-problem-statement)
3. [Competitive Landscape](#3-competitive-landscape)
4. [Domain Analysis: Global Tax Complexity](#4-domain-analysis-global-tax-complexity)
5. [Standards & Inspirations](#5-standards--inspirations)
6. [System Architecture](#6-system-architecture)
7. [Data Model](#7-data-model)
8. [Tax Obligation Taxonomy](#8-tax-obligation-taxonomy)
9. [Rule Engine](#9-rule-engine)
10. [API Design](#10-api-design)
11. [External AI Workflow Integration](#11-external-ai-workflow-integration)
12. [UI/Dashboard](#12-uidashboard)
13. [Edge Case Validation Scenarios](#13-edge-case-validation-scenarios)
14. [Technology Stack](#14-technology-stack)
15. [Implementation Phases](#15-implementation-phases)
16. [Open Questions](#16-open-questions)

---

## 1. Executive Summary

TaxLens is a production-ready, API-first platform for managing and calculating accommodation taxes across every jurisdiction worldwide. It targets OTAs (Booking.com, Expedia, Airbnb, etc.), hotel chains, property management systems, and travel tech companies that need accurate tax calculation for lodging and short-term rentals.

**Core USP:** Complete global coverage — every country, state, city, and sub-jurisdiction — with historical, current, and future tax data, managed through a jurisdiction-agnostic obligation taxonomy inspired by LegalRuleML, OpenFisca, and the Cambridge Regulatory Genome.

**Key differentiators vs. existing solutions:**
- Full global sub-national coverage (not just US + VAT)
- Hospitality-specific rule engine (not a general sales tax tool adapted for lodging)
- AI-powered monitoring via external workflow system (N8N-like) for tax law changes
- Temporal data model: historical rates, current rates, future effective dates, draft/pending rules
- Open API with detailed tax breakdowns per component
- Human-in-the-loop verification workflow for AI-suggested changes
- Jurisdiction-agnostic obligation taxonomy grounded in open standards

**Stack:** Python (FastAPI) + PostgreSQL (with extensions) + React. No Redis. No separate AI service — AI workflows are external.

---

## 2. Problem Statement

### The Scale of the Problem

There are conservatively **100,000+ distinct tax rules** globally affecting accommodation:
- **USA alone**: 16,000+ taxing jurisdictions with lodging-specific taxes
- **France**: 36,000+ communes each setting their own *taxe de sejour*
- **Italy**: 1,000+ municipalities with *imposta di soggiorno*
- **Rate changes**: 1,500-3,000 per year across all jurisdictions globally

### Where Existing Solutions Fail

| Gap | Impact |
|-----|--------|
| **International sub-national taxes** | No vendor comprehensively covers European city tourist taxes, Japanese accommodation taxes, or emerging Asian/African levies |
| **Hospitality-specific specialization** | Vertex, Thomson Reuters ONESOURCE are general indirect tax tools — they lack depth on lodging-specific levies (TOT, bed tax, tourism district taxes) |
| **The "long tail"** | ~20% of small/rural/newly-created taxing districts are frequently missed, representing disproportionate compliance risk |
| **Rate lag** | Even the best databases lag real-world changes by 30-90 days |
| **Component breakdown** | Most solutions return a single "lodging tax rate" rather than breaking out each component (state sales, city occupancy, tourism district, etc.) — critical for correct filing |
| **Temporal modeling** | Limited support for historical rate queries, future effective dates, and transitional periods |
| **STR vs. hotel differentiation** | Many jurisdictions now have different tax regimes for short-term rentals vs. traditional hotels — poorly modeled by existing tools |

### Who Needs This

| Persona | Need |
|---------|------|
| **OTAs** (Booking.com, Expedia) | Real-time tax calculation at booking, correct collection and remittance across thousands of jurisdictions |
| **STR platforms** (Airbnb, Vrbo) | VCA management, marketplace facilitator compliance, host tax obligation clarity |
| **Hotel chains** | Multi-property tax compliance, rate verification, filing automation |
| **PMS vendors** (Guesty, Hostaway) | Embedded tax calculation via API for their customers |
| **Tax advisory firms** | Research tool for lodging tax rates and rules across jurisdictions |
| **Government/regulators** | Verification and benchmarking of tax collection |

---

## 3. Competitive Landscape

### Direct Competitors

#### Avalara (MyLodgeTax + AvaTax)
- **Strengths:** Largest US coverage (23,000+ jurisdictions), API-first, filing/remittance services, acquired Sovos (2024) for VAT reporting
- **Weaknesses:** US-centric for lodging depth, international hospitality taxes are shallow, rate accuracy criticized for edge cases (special districts), MyLodgeTax oriented toward small operators not enterprise OTAs
- **Pricing:** AvaTax $5K-$100K+/yr enterprise; MyLodgeTax ~$20-30/mo per property

#### Vertex Inc.
- **Strengths:** Enterprise ERP integrations (SAP, Oracle), VAT in 300+ jurisdictions, strong with hotel chains running SAP
- **Weaknesses:** No dedicated hospitality vertical, less granular on US sub-national lodging taxes, enterprise-only ($50K-$250K+/yr)

#### Thomson Reuters ONESOURCE
- **Strengths:** Unified direct + indirect tax platform, large enterprise base
- **Weaknesses:** Not hospitality-specialized, long implementation cycles (6-18 months), enterprise pricing ($75K-$300K+/yr)

#### Stripe Tax / TaxJar
- **Strengths:** Developer-friendly API, simple pricing ($0.005/transaction)
- **Weaknesses:** E-commerce focused, limited lodging tax coverage, no filing/remittance

### How OTAs Handle Tax Today

**Booking.com:** Historically pure agency model (hotel handles tax). Shifting toward payment facilitation, making tax obligations more complex. Tax compliance largely decentralized to properties.

**Expedia:** Operated merchant model extensively — led to massive litigation over whether tax applies to wholesale or retail rate. Moving toward hybrid model. Built internal tax engineering teams.

**Airbnb:** Voluntary Collection Agreements (VCAs) with ~700+ jurisdictions. Built significant in-house tax technology. Still has major gaps — many cities/counties and most international sub-national jurisdictions are NOT covered.

### The Opportunity

The Avalara+Sovos merger creates a dominant but monolithic player. There's a clear gap for:
1. A purpose-built hospitality tax platform (not adapted from general sales tax)
2. True global sub-national coverage (not just US + national VAT)
3. AI-powered monitoring to close the rate-lag gap
4. Modern API-first architecture for the developer ecosystem
5. Transparent, component-level tax breakdowns for correct multi-authority filing

---

## 4. Domain Analysis: Global Tax Complexity

### Tax Types Applied to Accommodation

| Tax Type | Calculation Method | Examples |
|----------|-------------------|----------|
| **Occupancy/Lodging Tax** | Percentage of room rate | US state/city TOT (1-15%+) |
| **Tourism Tax/Tourist Levy** | Flat per-person-per-night | France *taxe de sejour* (EUR 0.20-4.00), Dubai Tourism Dirham (AED 7-20) |
| **VAT/GST** | Percentage (often reduced rate) | EU (5-25%), Japan (10%), UAE (5%) |
| **Sales Tax on Lodging** | Percentage (general rate) | US states applying general sales tax to rooms |
| **Environmental/Sustainability Tax** | Flat or percentage | Balearic Islands (EUR 1-4), Bhutan ($100/night), Maldives ($6/person/night) |
| **Special District Tax** | Percentage or flat | Convention center districts, tourism improvement districts, stadium financing |
| **Municipal Fee** | Percentage | Dubai municipality fee (7%), Amsterdam tourist tax (7%) |
| **Resort/Mandatory Fees** | Flat per-night | Las Vegas resort fees ($30-50+) — taxability varies |

### Jurisdiction Complexity Showcase

**New York City** — ~14.75% + $1.50/night flat fee:
- NY State sales tax: 4%
- NYC local sales tax: 4.5%
- MCTD surcharge: 0.375%
- NYC hotel room occupancy tax: 5.875%
- Flat fee: $1.50/room/night (rooms $40+)

**Chicago** — can exceed 17.5%:
- Illinois state hotel tax: 6%
- Cook County hotel tax: 5.5%
- City of Chicago accommodation tax: 4.5%
- McCormick Place/MPEA tax: 2.5%
- Additional special service area taxes

**Dubai** — can reach 22%+:
- 5% VAT
- 7% Municipality Fee
- 10% Service Charge
- Tourism Dirham: AED 7-20/night by classification

**Bali** — can exceed 31% effective burden:
- 11% national VAT
- 10% provincial hotel/restaurant tax
- Foreign tourist levy: IDR 150,000 (~$10)
- 10% service charge

### Rule Complexity Matrix

| Complexity Factor | Examples | Impact on System Design |
|-------------------|----------|------------------------|
| **Property type differentiation** | France: 9+ categories with different rates; US: hotel vs STR different regimes | Property classification taxonomy required |
| **Star rating tiers** | Dubai: AED 7-20 by stars; Greece: EUR 0.50-4.00 by stars | Rating/classification attribute on properties |
| **Price thresholds** | Japan: exempt under JPY 10K; India: 12% vs 18% at INR 7,500 | Conditional rate rules with amount comparisons |
| **Stay length exemptions** | CA: exempt after 30 days; NYC: 90 days; Rome: capped at 10 nights | Duration-based rule conditions |
| **Seasonal variation** | Venice: higher May-Oct; Balearic Islands: high/low season rates | Date-range-aware rate variants |
| **Guest exemptions** | Government, military, diplomatic, non-profit, children (varying age thresholds), medical, religious | Exemption certificate/type system |
| **Tax-on-tax (cascading)** | Some US jurisdictions calculate city tax on base+state tax; Mexico IVA on base+lodging tax | Calculation ordering with compound base |
| **Bundled services** | Germany: room at 7% VAT, breakfast at 19% VAT — mandatory separation | Service component allocation rules |
| **Marketplace facilitator** | ~40+ US states require platforms to collect; EU ViDA directive (2027) | Platform obligation tracking per jurisdiction |
| **Currency/FX** | Booking in EUR, remittance in local currency | FX rate at time of stay for calculation |

---

## 5. Standards & Inspirations

Our tax obligation taxonomy is not invented from scratch. It draws from established standards for modeling legal rules and regulatory obligations in a jurisdiction-agnostic way.

### 5.1 LegalRuleML (OASIS Standard)

**What we borrow:** The deontic modeling pattern and temporal dimensions.

LegalRuleML distinguishes:
- **PrescriptiveStatement**: "Bearer X is obligated to pay Y" — maps to our tax obligations
- **ConstitutiveStatement**: "What counts as a taxable accommodation" — maps to our property classifications and jurisdiction definitions
- **Defeasibility**: Rules can be overridden by more specific rules — maps to our exemption/exception model where "all guests pay tourist tax" is defeasible by "except children under 12"

LegalRuleML's **three temporal dimensions** directly inform our model:
1. **Enacted date** — when the law was passed
2. **Effective date** — when it takes legal effect (may differ from enacted)
3. **Applicability date** — when conditions can be satisfied

We also adopt the **Context element** pattern: every rule is wrapped with jurisdiction scope + temporal scope + authority reference.

### 5.2 OpenFisca

**What we borrow:** Parameter versioning, scale types, and the formula/variable model.

OpenFisca's parameter model stores tax values as **dated YAML**:
```yaml
values:
  2020-01-01:
    value: 0.14
  2024-07-01:
    value: 0.145
```

This directly maps to our `tax_rates.effective_range` with daterange.

OpenFisca's **three scale types** cover all our rate calculation patterns:
- **Marginal rate scale**: Different rates per bracket (progressive taxation)
- **Single amount scale**: Returns a fixed value for the matching bracket — maps to Japan's accommodation tax (JPY 100/200/1000 by price tier)
- **Marginal amount scale**: Cumulative amounts across brackets

We adopt the **entity model** concept: Guest, Property, Stay, and Operator as the core entities that rules evaluate against.

### 5.3 Cambridge Regulatory Genome

**What we borrow:** The jurisdiction-agnostic root taxonomy + jurisdiction-specific extensions pattern.

The CRG defines:
- **Level 0-2**: Core obligation taxonomy (jurisdiction-agnostic concepts)
- **Level 3+**: Jurisdiction-specific extensions for granular local rules

Applied to our system:
- **Level 0**: "Accommodation tax obligation" (universal concept)
- **Level 1**: Tax category (occupancy, tourism levy, VAT, special district, environmental)
- **Level 2**: Calculation method (percentage, flat per-night, flat per-person-per-night, tiered, compound)
- **Level 3+**: Jurisdiction-specific rules (NYC flat fee of $1.50 for rooms >$40, Venice seasonal variation, Tokyo price-tier thresholds)

This means our core schema handles any jurisdiction without modification — only the data changes.

### 5.4 Catala (Inria)

**What we borrow:** Default logic for exception handling.

Catala's key insight: legal rules follow a **default + exception** pattern:
```
definition tax_rate equals 14%
exception when guest_type = government: tax_rate equals 0%
exception when stay_length >= 30 days: tax_rate equals 0%
```

This maps directly to our rule engine:
- Base tax rates are the "default"
- Tax rules with `rule_type = 'exemption'` are "exceptions" with priority ordering
- If multiple exceptions apply, the highest-priority one wins
- If no exception applies, the default fires

### 5.5 Akoma Ntoso (OASIS LegalDocML)

**What we borrow:** Jurisdiction identification scheme and legal reference format.

- Jurisdiction codes follow ISO 3166-1 (country) + ISO 3166-2 (subdivision) — we extend with city/district codes
- Legal references are structured as URIs: `/akn/{jurisdiction}/{docType}/{date}/{id}`
- We adapt this for `source_url` and `legal_reference` fields to ensure every rate is traceable to its legal authority

### 5.6 Design Principle Summary

| Concern | Pattern | Source |
|---------|---------|--------|
| **Rule semantics** | Obligation/Exception with defeasibility | LegalRuleML + Catala |
| **Temporal versioning** | Dated parameter values with enacted/effective/applicability dates | OpenFisca + LegalRuleML |
| **Rate calculation types** | Percentage, flat, tiered (single amount scale, marginal rate scale) | OpenFisca |
| **Taxonomy hierarchy** | Jurisdiction-agnostic root (L0-L2) + jurisdiction extensions (L3+) | Cambridge Regulatory Genome |
| **Jurisdiction identification** | ISO 3166 codes extended with city/district | Akoma Ntoso |
| **Legal traceability** | URI-based references to legislation | Akoma Ntoso |
| **Entity model** | Guest, Property, Stay, Operator | OpenFisca entities |
| **Exception handling** | Default rules + prioritized exceptions | Catala default logic |

---

## 6. System Architecture

### Three Components

The system is split into three cleanly separated components:

```
┌─────────────────────────────────────────────────────────────────┐
│                     1. REACT UI (Frontend)                       │
│                                                                  │
│  Jurisdiction Explorer │ Rate Browser │ Change Review Dashboard  │
│  Tax Calculator Tool   │ Audit Trail  │ Analytics & Coverage     │
│                                                                  │
│  Consumes the Python API. No business logic in the frontend.     │
└──────────────────────────────┬──────────────────────────────────┘
                               │ HTTP/REST
┌──────────────────────────────▼──────────────────────────────────┐
│                 2. PYTHON API (FastAPI Backend)                   │
│                                                                  │
│  ┌────────────┐  ┌────────────┐  ┌────────────┐  ┌───────────┐ │
│  │ Jurisdiction│  │ Tax Rate   │  │ Tax        │  │ AI        │ │
│  │ Management │  │ Management │  │ Calculation│  │ Integration│ │
│  │ API        │  │ API        │  │ Engine     │  │ Webhooks  │ │
│  └──────┬─────┘  └──────┬─────┘  └──────┬─────┘  └─────┬─────┘ │
│         │               │               │              │        │
│  ┌──────▼───────────────▼───────────────▼──────────────▼──────┐ │
│  │                    Rule Engine (Library)                     │ │
│  │  Jurisdiction Resolver → Rate Collector → Condition         │ │
│  │  Evaluator → Exemption Checker → Tax Calculator             │ │
│  └──────────────────────────┬──────────────────────────────────┘ │
│                              │                                   │
│  ┌──────────────────────────▼──────────────────────────────────┐ │
│  │              PostgreSQL (Single Source of Truth)              │ │
│  │                                                              │ │
│  │  Jurisdictions (ltree) │ Tax Rates (daterange)               │ │
│  │  Tax Rules (JSONB)     │ Audit Log                           │ │
│  │  Sources & Changes     │ PostGIS boundaries                  │ │
│  └──────────────────────────────────────────────────────────────┘ │
└──────────────────────────────┬──────────────────────────────────┘
                               │ REST API calls (bidirectional)
┌──────────────────────────────▼──────────────────────────────────┐
│            3. EXTERNAL AI WORKFLOW (N8N-like system)              │
│                                                                  │
│  Lives outside TaxLens. Uses our API to read/write data.         │
│  Our backend can trigger workflows via webhooks.                 │
│                                                                  │
│  Workflows:                                                      │
│  ┌─────────────────────────────────────────────────────────┐     │
│  │ A. Suggest Sub-Jurisdictions                             │     │
│  │    Input: jurisdiction_code (e.g., "US")                 │     │
│  │    LLM generates list of sub-jurisdictions               │     │
│  │    Calls POST /v1/jurisdictions/bulk to create them      │     │
│  └─────────────────────────────────────────────────────────┘     │
│  ┌─────────────────────────────────────────────────────────┐     │
│  │ B. Suggest Monitoring Sources                            │     │
│  │    Input: jurisdiction_code                              │     │
│  │    LLM generates list of government/official URLs        │     │
│  │    Calls POST /v1/sources/bulk to register them          │     │
│  └─────────────────────────────────────────────────────────┘     │
│  ┌─────────────────────────────────────────────────────────┐     │
│  │ C. Scrape & Structure Taxes (weekly/monthly)             │     │
│  │    Reads sources from GET /v1/sources                    │     │
│  │    Scrapes each URL, LLM extracts structured tax data    │     │
│  │    Calls POST /v1/changes/bulk with extracted data       │     │
│  │    Results land as "pending_review" in the system        │     │
│  └─────────────────────────────────────────────────────────┘     │
└─────────────────────────────────────────────────────────────────┘
```

### Key Design Principles

1. **Never lose history.** Every rate, rule, and calculation is reproducible for any past date. Immutable records with version chains.
2. **Component-level breakdown.** Every calculation returns each tax component separately — critical for multi-authority filing.
3. **API-first.** The UI is a consumer of the API. Every operation available in the UI is available via API.
4. **Temporal-native.** First-class support for "what was the tax on date X?" and "what will the tax be starting date Y?"
5. **Auditable.** Every calculation explains which rules fired and why, traceable to legal references.
6. **Postgres is the truth.** No Redis, no external caches. Postgres handles caching through materialized views, connection pooling, and proper indexing.
7. **AI is external.** The AI workflow system (N8N-like) lives outside TaxLens. It calls our API. We expose webhooks for it to trigger and endpoints for it to push data. This keeps our core system deterministic and testable.

### Rule Lifecycle States

Tax rates and rules move through these states:

```
                          ┌──────────────┐
                          │   ai_draft   │  ← AI workflow suggested this
                          │              │    (not yet reviewed by human)
                          └──────┬───────┘
                                 │ human reviews
                    ┌────────────┼────────────┐
                    │            │            │
              ┌─────▼──┐  ┌─────▼──┐  ┌─────▼──────┐
              │approved│  │rejected│  │needs_review │
              │(draft) │  │        │  │             │
              └───┬────┘  └────────┘  └─────────────┘
                  │
      ┌───────────┼───────────────┐
      │                           │
┌─────▼──────┐           ┌───────▼────────┐
│  scheduled │           │    active      │
│            │           │                │
│ effective  │──(date)──▶│ currently in   │
│ in future  │  arrives  │ force          │
└────────────┘           └───────┬────────┘
                                 │ superseded by new version
                         ┌───────▼────────┐
                         │  superseded    │
                         │  (historical)  │
                         └────────────────┘
```

States:
- **`ai_draft`** — AI workflow suggested this rate/rule; not yet reviewed
- **`approved`** — Human approved but may not be in effect yet
- **`scheduled`** — Approved and will become active on a future effective date
- **`active`** — Currently in force; used for tax calculations
- **`superseded`** — Was active, now replaced by a newer version (kept for historical queries)
- **`rejected`** — AI suggestion was rejected by human reviewer
- **`needs_review`** — Flagged for additional verification

Only `active` rules participate in tax calculations. `scheduled` rules are visible in the API for "future rate" queries.

---

## 7. Data Model

### Core PostgreSQL Schema

#### Jurisdictions

Uses PostgreSQL `ltree` extension for hierarchical queries and PostGIS for geospatial resolution.

```sql
CREATE EXTENSION IF NOT EXISTS ltree;
CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS btree_gist;
CREATE EXTENSION IF NOT EXISTS pg_trgm;

CREATE TABLE jurisdictions (
    id              BIGSERIAL PRIMARY KEY,
    code            TEXT NOT NULL UNIQUE,         -- ISO-based: 'US-NY-NYC', 'FR-IDF-75056',
                                                 -- 'JP-13-TOKYO' (ISO 3166-1 + 3166-2 + local)
    name            TEXT NOT NULL,                -- 'New York City'
    local_name      TEXT,                         -- Name in local language
    jurisdiction_type TEXT NOT NULL,              -- 'country', 'state', 'province', 'region',
                                                 -- 'county', 'city', 'municipality',
                                                 -- 'special_district', 'zone'
    path            ltree NOT NULL,              -- 'US.NY.NYC'
    parent_id       BIGINT REFERENCES jurisdictions(id),
    country_code    CHAR(2) NOT NULL,            -- ISO 3166-1 alpha-2
    subdivision_code TEXT,                        -- ISO 3166-2
    timezone        TEXT,                         -- 'America/New_York'
    currency_code   CHAR(3) NOT NULL,            -- ISO 4217
    geo_boundary    GEOMETRY(MultiPolygon, 4326), -- PostGIS boundary (optional)
    status          TEXT NOT NULL DEFAULT 'active', -- 'active', 'dissolved', 'merged'
    metadata        JSONB DEFAULT '{}',          -- Population, tourism stats, aliases, etc.
    created_by      TEXT NOT NULL DEFAULT 'system',
    created_at      TIMESTAMPTZ DEFAULT now(),
    updated_at      TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_jurisdictions_path ON jurisdictions USING GIST (path);
CREATE INDEX idx_jurisdictions_geo ON jurisdictions USING GIST (geo_boundary);
CREATE INDEX idx_jurisdictions_country ON jurisdictions (country_code);
CREATE INDEX idx_jurisdictions_type ON jurisdictions (jurisdiction_type);
CREATE INDEX idx_jurisdictions_parent ON jurisdictions (parent_id);
CREATE INDEX idx_jurisdictions_name_trgm ON jurisdictions USING GIN (name gin_trgm_ops);
```

#### Tax Categories (Obligation Taxonomy — Level 0-2)

Jurisdiction-agnostic taxonomy of accommodation tax obligation types, inspired by Cambridge Regulatory Genome levels.

```sql
CREATE TABLE tax_categories (
    id              BIGSERIAL PRIMARY KEY,
    code            TEXT NOT NULL UNIQUE,
    name            TEXT NOT NULL,
    description     TEXT,

    -- CRG-inspired taxonomy levels
    level_0         TEXT NOT NULL,               -- 'accommodation_tax' (always)
    level_1         TEXT NOT NULL,               -- 'occupancy', 'tourism_levy', 'vat',
                                                 -- 'sales_tax', 'environmental', 'special_district',
                                                 -- 'municipal_fee', 'service_charge'
    level_2         TEXT NOT NULL,               -- Calculation method:
                                                 -- 'percentage_of_rate', 'flat_per_night',
                                                 -- 'flat_per_person_per_night', 'flat_per_room_per_night',
                                                 -- 'tiered_by_price', 'tiered_by_classification',
                                                 -- 'compound_percentage'

    -- How the tax base is determined
    base_type       TEXT NOT NULL DEFAULT 'room_rate',
                                                 -- 'room_rate' — tax on nightly rate
                                                 -- 'total_stay' — tax on total accommodation cost
                                                 -- 'base_plus_prior_taxes' — cascading/compound
                                                 -- 'per_unit' — flat amount per night/person

    metadata        JSONB DEFAULT '{}'
);
```

#### Tax Rates (Temporal, Versioned, with Lifecycle States)

```sql
CREATE TABLE tax_rates (
    id              BIGSERIAL PRIMARY KEY,
    jurisdiction_id BIGINT NOT NULL REFERENCES jurisdictions(id),
    tax_category_id BIGINT NOT NULL REFERENCES tax_categories(id),

    -- Rate definition
    rate_type       TEXT NOT NULL,               -- 'percentage', 'flat', 'tiered'
    rate_value      NUMERIC(12,6),               -- 0.14 for 14%, or 1.50 for $1.50 flat
    currency_code   CHAR(3),                     -- For flat rates: 'USD', 'EUR', 'JPY', etc.

    -- Tiered rates (OpenFisca single_amount_scale / marginal_rate_scale)
    -- e.g., Tokyo: [{"min": 0, "max": 10000, "value": 0}, {"min": 10000, "max": 15000, "value": 100}, {"min": 15000, "max": null, "value": 200}]
    -- e.g., India GST: [{"min": 0, "max": 7500, "rate": 0.12}, {"min": 7500, "max": null, "rate": 0.18}]
    tiers           JSONB,
    tier_type       TEXT,                        -- 'single_amount' (flat per bracket, like Tokyo)
                                                 -- 'marginal_rate' (different % per bracket, like income tax)
                                                 -- 'threshold' (rate changes entirely above threshold, like India GST)

    -- Temporal validity (LegalRuleML three temporal dimensions)
    enacted_date    DATE,                         -- When the law was passed
    effective_range daterange NOT NULL,           -- [effective_from, effective_to) — when rule is in force
    applicability_start DATE,                     -- When conditions can first be satisfied (usually = effective_from)
    announcement_date DATE,                       -- When publicly announced

    -- Calculation ordering (for tax-on-tax / compound taxes)
    calculation_order INT NOT NULL DEFAULT 100,   -- Lower = calculated first
    base_includes   TEXT[] DEFAULT '{base_amount}', -- What the tax base includes
                                                    -- '{base_amount}' or
                                                    -- '{base_amount,state_sales_tax}'

    -- Legal reference (Akoma Ntoso-inspired)
    legal_reference TEXT,                         -- Statute/ordinance citation
    legal_uri       TEXT,                         -- Structured URI to legislation
    source_url      TEXT,                         -- URL to official source
    authority_name  TEXT,                         -- 'NYC Department of Finance'

    -- Versioning & Lifecycle
    version         INT NOT NULL DEFAULT 1,
    supersedes_id   BIGINT REFERENCES tax_rates(id),
    status          TEXT NOT NULL DEFAULT 'ai_draft',
                    -- 'ai_draft' — AI suggested, not yet reviewed
                    -- 'approved' — human approved
                    -- 'scheduled' — approved, effective in future
                    -- 'active' — currently in force
                    -- 'superseded' — replaced by newer version
                    -- 'rejected' — AI suggestion rejected
                    -- 'needs_review' — flagged for verification

    -- Audit
    created_by      TEXT NOT NULL,               -- 'system', 'ai_workflow', 'user:john@...'
    reviewed_by     TEXT,
    reviewed_at     TIMESTAMPTZ,
    review_notes    TEXT,
    created_at      TIMESTAMPTZ DEFAULT now(),
    updated_at      TIMESTAMPTZ DEFAULT now(),

    -- Prevent overlapping ACTIVE rates for same jurisdiction + category
    EXCLUDE USING GIST (
        jurisdiction_id WITH =,
        tax_category_id WITH =,
        effective_range WITH &&
    ) WHERE (status = 'active')
);

CREATE INDEX idx_tax_rates_jurisdiction ON tax_rates (jurisdiction_id);
CREATE INDEX idx_tax_rates_effective ON tax_rates USING GIST (effective_range);
CREATE INDEX idx_tax_rates_status ON tax_rates (status);
CREATE INDEX idx_tax_rates_active ON tax_rates (jurisdiction_id, tax_category_id)
    WHERE status = 'active';
CREATE INDEX idx_tax_rates_scheduled ON tax_rates (jurisdiction_id)
    WHERE status = 'scheduled';
```

#### Tax Rules (Conditions, Exemptions, Exceptions)

Following LegalRuleML's defeasibility model and Catala's default-logic exceptions.

```sql
CREATE TABLE tax_rules (
    id              BIGSERIAL PRIMARY KEY,
    tax_rate_id     BIGINT REFERENCES tax_rates(id),
    jurisdiction_id BIGINT NOT NULL REFERENCES jurisdictions(id),

    -- LegalRuleML-inspired rule classification
    rule_type       TEXT NOT NULL,               -- 'condition' — when the base rate applies
                                                 -- 'exemption' — defeasible exception (zeroes the tax)
                                                 -- 'reduction' — reduces the rate
                                                 -- 'surcharge' — adds to the rate
                                                 -- 'cap' — limits tax (max nights, max amount)
                                                 -- 'override' — replaces the rate entirely
                                                 -- 'threshold' — rate changes above/below value

    -- Catala-inspired priority: higher priority exceptions override lower
    priority        INT NOT NULL DEFAULT 0,
    name            TEXT NOT NULL,               -- 'Government employee exemption'
    description     TEXT,

    -- Conditions as structured JSONB (evaluated by rule engine)
    conditions      JSONB NOT NULL DEFAULT '{}',
    -- Action to take when conditions match
    action          JSONB NOT NULL DEFAULT '{}',

    -- Temporal validity
    effective_range daterange NOT NULL,
    enacted_date    DATE,

    -- Legal traceability
    legal_reference TEXT,
    legal_uri       TEXT,
    authority_name  TEXT,

    -- Lifecycle (same states as tax_rates)
    status          TEXT NOT NULL DEFAULT 'active',
    version         INT NOT NULL DEFAULT 1,
    supersedes_id   BIGINT REFERENCES tax_rules(id),

    created_by      TEXT NOT NULL,
    reviewed_by     TEXT,
    reviewed_at     TIMESTAMPTZ,
    created_at      TIMESTAMPTZ DEFAULT now(),
    updated_at      TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_tax_rules_jurisdiction ON tax_rules (jurisdiction_id);
CREATE INDEX idx_tax_rules_rate ON tax_rules (tax_rate_id);
CREATE INDEX idx_tax_rules_type ON tax_rules (rule_type);
CREATE INDEX idx_tax_rules_status ON tax_rules (status);
```

#### Condition & Action JSONB Schemas

**Condition Schema** (used in `tax_rules.conditions`):

```jsonc
// Logical combinators with nesting support
{
  "operator": "AND",           // "AND" | "OR"
  "rules": [
    {"field": "stay_length_days", "op": ">=", "value": 30},
    {"field": "property_type", "op": "in", "value": ["hotel", "motel", "str"]},
    {
      "operator": "OR",       // Nested group
      "rules": [
        {"field": "guest_type", "op": "==", "value": "government"},
        {"field": "guest_type", "op": "==", "value": "diplomatic"}
      ]
    }
  ]
}
```

Supported fields:

| Field | Type | Description |
|-------|------|-------------|
| `property_type` | string | hotel, motel, str, bnb, hostel, resort, campsite, furnished_rental |
| `star_rating` | number | 1-5 classification |
| `nightly_rate` | decimal | Room rate per night in local currency |
| `total_stay_amount` | decimal | Total accommodation cost |
| `stay_length_days` | integer | Total consecutive nights |
| `stay_month` | integer | 1-12, for seasonal rules |
| `stay_date` | date | For event-based surcharges |
| `guest_type` | string | standard, government, military, diplomatic, nonprofit, student |
| `guest_age` | integer | For child exemptions |
| `guest_nationality` | string | ISO country code — for resident vs tourist rules |
| `room_count` | integer | Property's total room count |
| `is_marketplace` | boolean | Booked through marketplace facilitator |
| `platform_type` | string | ota, direct, property_manager |
| `is_bundled` | boolean | Part of a package (flight+hotel) |
| `number_of_guests` | integer | For per-person taxes |

Supported operators: `==`, `!=`, `>`, `>=`, `<`, `<=`, `in`, `not_in`, `between`

**Action Schema** (used in `tax_rules.action`):

```jsonc
// Full exemption
{"type": "exempt", "reason": "Long-term stay exemption per CA Rev & Tax Code §7280"}

// Rate override
{"type": "override_rate", "rate_value": 0.08, "rate_type": "percentage"}

// Night cap (taxe de sejour style — max taxable nights)
{"type": "cap", "max_nights": 10, "description": "Tax capped at 10 consecutive nights"}

// Amount cap
{"type": "cap_amount", "max_amount": 500.00, "currency": "EUR"}

// Surcharge (additional amount on top of base)
{"type": "surcharge", "rate_value": 0.0125, "rate_type": "percentage"}

// Reduction (percentage off the base rate)
{"type": "reduction", "reduction_percent": 0.50, "description": "Low season 50% reduction"}

// Per-person modifier (multiply base by guest count)
{"type": "per_person", "description": "Tax applies per person per night"}
```

#### Property Classifications

```sql
CREATE TABLE property_classifications (
    id              BIGSERIAL PRIMARY KEY,
    code            TEXT NOT NULL UNIQUE,         -- 'hotel', 'motel', 'bnb', 'str',
                                                 -- 'hostel', 'resort', 'campsite',
                                                 -- 'furnished_rental', 'agriturismo', 'palace'
    name            TEXT NOT NULL,
    description     TEXT,
    -- Maps to local classification systems per jurisdiction
    local_mappings  JSONB DEFAULT '{}'           -- {"FR": "meublé de tourisme",
                                                 --  "IT": "casa vacanze",
                                                 --  "JP": "旅館"}
);
```

#### Monitoring Sources & AI-Detected Changes

```sql
-- Registry of government/official sources to monitor
CREATE TABLE monitored_sources (
    id              BIGSERIAL PRIMARY KEY,
    jurisdiction_id BIGINT REFERENCES jurisdictions(id),
    url             TEXT NOT NULL,
    source_type     TEXT NOT NULL,               -- 'government_website', 'legislation_db',
                                                 -- 'gazette', 'tax_authority', 'news'
    language        TEXT NOT NULL DEFAULT 'en',   -- ISO 639-1
    check_frequency INTERVAL NOT NULL DEFAULT '7 days',
    last_checked_at TIMESTAMPTZ,
    last_content_hash TEXT,                      -- SHA-256 for change detection
    status          TEXT NOT NULL DEFAULT 'active', -- 'active', 'paused', 'broken'
    metadata        JSONB DEFAULT '{}',
    created_by      TEXT NOT NULL DEFAULT 'system',
    created_at      TIMESTAMPTZ DEFAULT now(),
    updated_at      TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_sources_jurisdiction ON monitored_sources (jurisdiction_id);
CREATE INDEX idx_sources_status ON monitored_sources (status);

-- AI-detected changes pending review
CREATE TABLE detected_changes (
    id              BIGSERIAL PRIMARY KEY,
    source_id       BIGINT REFERENCES monitored_sources(id),
    jurisdiction_id BIGINT REFERENCES jurisdictions(id),

    change_type     TEXT NOT NULL,               -- 'new_rate', 'rate_change', 'new_rule',
                                                 -- 'new_exemption', 'rate_expiry',
                                                 -- 'new_jurisdiction'
    detected_at     TIMESTAMPTZ DEFAULT now(),

    -- AI extraction results (structured JSON from LLM)
    extracted_data  JSONB NOT NULL,
    confidence      NUMERIC(3,2) NOT NULL,       -- 0.00-1.00
    source_quote    TEXT,                        -- Exact text from source document
    source_snapshot_url TEXT,                    -- Link to archived page content

    -- Review workflow
    review_status   TEXT NOT NULL DEFAULT 'pending', -- 'pending', 'approved', 'rejected',
                                                     -- 'needs_info', 'auto_applied'
    reviewed_by     TEXT,
    reviewed_at     TIMESTAMPTZ,
    review_notes    TEXT,

    -- If approved, link to created/updated entities
    applied_rate_id BIGINT REFERENCES tax_rates(id),
    applied_rule_id BIGINT REFERENCES tax_rules(id),

    created_at      TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_changes_status ON detected_changes (review_status);
CREATE INDEX idx_changes_jurisdiction ON detected_changes (jurisdiction_id);
CREATE INDEX idx_changes_detected ON detected_changes (detected_at);
```

#### Audit Log

```sql
CREATE TABLE audit_log (
    id              BIGSERIAL PRIMARY KEY,
    entity_type     TEXT NOT NULL,               -- 'tax_rate', 'tax_rule', 'jurisdiction',
                                                 -- 'detected_change', 'source'
    entity_id       BIGINT NOT NULL,
    action          TEXT NOT NULL,               -- 'created', 'updated', 'status_changed',
                                                 -- 'approved', 'rejected', 'superseded'
    old_values      JSONB,
    new_values      JSONB,
    changed_by      TEXT NOT NULL,               -- 'system', 'ai_workflow', 'user:email'
    change_source   TEXT NOT NULL,               -- 'manual', 'ai_workflow', 'bulk_import',
                                                 -- 'api', 'scheduled_transition'
    change_reason   TEXT,
    source_reference TEXT,                       -- Link to legislation or AI detection
    created_at      TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_audit_entity ON audit_log (entity_type, entity_id);
CREATE INDEX idx_audit_time ON audit_log (created_at);
CREATE INDEX idx_audit_source ON audit_log (change_source);
```

### Entity Relationship Summary

```
jurisdictions (ltree hierarchy)
    ├── tax_rates (temporal, versioned, lifecycle states)
    │       └── tax_rules (conditions, exemptions — defeasible)
    ├── monitored_sources
    │       └── detected_changes (AI extraction → review → apply)
    └── (PostGIS geo resolution)

tax_categories (jurisdiction-agnostic taxonomy, L0-L2)

property_classifications (global taxonomy with local mappings)

audit_log (cross-entity immutable trail)
```

---

## 8. Tax Obligation Taxonomy

### Universal Categories (L0-L2)

These are jurisdiction-agnostic and cover every type of accommodation tax worldwide.

| Code | L1 (Type) | L2 (Calculation Method) | Real Examples |
|------|-----------|------------------------|---------------|
| `occ_pct` | occupancy | percentage_of_rate | US state/city TOT, Amsterdam 7% |
| `occ_flat_night` | occupancy | flat_per_room_per_night | NYC $1.50/room/night |
| `tourism_flat_night` | tourism_levy | flat_per_night | France *taxe de sejour* |
| `tourism_flat_person` | tourism_levy | flat_per_person_per_night | Italy *imposta di soggiorno* |
| `tourism_pct` | tourism_levy | percentage_of_rate | Amsterdam 7% |
| `vat_standard` | vat | percentage_of_rate | UK 20%, UAE 5% |
| `vat_reduced` | vat | percentage_of_rate | France 10%, Germany 7% |
| `sales_tax` | sales_tax | percentage_of_rate | US state sales tax on lodging |
| `env_flat` | environmental | flat_per_night | Maldives Green Tax $6/night |
| `env_flat_person` | environmental | flat_per_person_per_night | Bhutan SDF $100/person/night |
| `env_pct` | environmental | percentage_of_rate | Balearic Islands sustainable tourism tax |
| `district_pct` | special_district | percentage_of_rate | McCormick Place tax, TID assessments |
| `district_flat` | special_district | flat_per_night | Convention center flat fees |
| `municipal_pct` | municipal_fee | percentage_of_rate | Dubai Municipality Fee 7% |
| `service_pct` | service_charge | percentage_of_rate | Dubai 10% service charge |
| `tier_price` | occupancy | tiered_by_price | Tokyo/Kyoto accommodation tax |
| `tier_class` | tourism_levy | tiered_by_classification | Dubai Tourism Dirham by star rating |
| `compound_pct` | occupancy | compound_percentage | Tax-on-tax cascading scenarios |

### Jurisdiction-Specific Extensions (L3+)

Each jurisdiction can have rules that add specificity:

```
L0: accommodation_tax
  L1: occupancy
    L2: percentage_of_rate
      L3 (US-NY-NYC): NYC Hotel Room Occupancy Tax — 5.875%
      L3 (US-IL-CHI): Chicago Hotel Accommodation Tax — 4.5%
      L3 (NL-NH-AMS): Amsterdam Tourist Tax — 7%
  L1: tourism_levy
    L2: flat_per_person_per_night
      L3 (IT-RM): Rome imposta di soggiorno — EUR 3-7 by star rating
      L3 (FR-75056): Paris taxe de séjour — EUR 0.20-4.00 by classification
      L3 (JP-13-TOKYO): Tokyo shukuhaku-zei — JPY 0/100/200 by price tier
```

---

## 9. Rule Engine

### Architecture

The rule engine is a Python library embedded in the FastAPI application. It follows a **decision table pattern** stored in Postgres, evaluated by typed handlers in Python code.

### Calculation Pipeline

```
Input (TaxCalculationRequest)
    │
    ▼
┌─────────────────────────────┐
│ 1. Jurisdiction Resolution  │  Given jurisdiction_code → find all ancestor
│                             │  jurisdictions using ltree:
│                             │  SELECT * FROM jurisdictions
│                             │  WHERE path @> 'US.NY.NYC'
│                             │  Returns: [US, US-NY, US-NY-NYC, US-NY-MCTD]
└──────────┬──────────────────┘
           │
           ▼
┌─────────────────────────────┐
│ 2. Rate Collection          │  For each jurisdiction, fetch all tax_rates
│                             │  WHERE status = 'active'
│                             │  AND effective_range @> stay_date
│                             │  ORDER BY calculation_order
└──────────┬──────────────────┘
           │
           ▼
┌─────────────────────────────┐
│ 3. Rule Evaluation          │  For each rate, fetch associated tax_rules
│    (Catala default logic)   │  WHERE status = 'active'
│                             │  AND effective_range @> stay_date
│                             │  ORDER BY priority DESC
│                             │
│                             │  Evaluate conditions against booking context.
│                             │  First matching exemption wins (highest priority).
│                             │  Apply caps, reductions, surcharges.
└──────────┬──────────────────┘
           │
           ▼
┌─────────────────────────────┐
│ 4. Tax Calculation          │  For each applicable rate (in calculation_order):
│                             │  - Determine tax base from base_includes
│                             │  - Apply rate (percentage, flat, or tiered)
│                             │  - Handle per-person/per-night multipliers
│                             │  - Accumulate into ordered breakdown
└──────────┬──────────────────┘
           │
           ▼
┌─────────────────────────────┐
│ 5. Result Assembly          │  Produce TaxBreakdown:
│                             │  - Each component with jurisdiction, authority,
│                             │    rate, amount, legal reference
│                             │  - Total tax amount
│                             │  - Effective combined rate
│                             │  - Rule trace (which rules fired and why)
└─────────────────────────────┘
```

### Rule Evaluation (Default Logic)

```python
from decimal import Decimal
from dataclasses import dataclass

@dataclass
class BookingContext:
    jurisdiction_code: str
    stay_date: date
    checkout_date: date
    nightly_rate: Decimal
    nights: int
    property_type: str
    star_rating: int | None = None
    guest_type: str = "standard"
    guest_age: int | None = None
    guest_nationality: str | None = None
    number_of_guests: int = 1
    is_marketplace: bool = False
    platform_type: str = "direct"
    is_bundled: bool = False

    @property
    def stay_length_days(self) -> int:
        return self.nights

    @property
    def stay_month(self) -> int:
        return self.stay_date.month

    @property
    def total_stay_amount(self) -> Decimal:
        return self.nightly_rate * self.nights


class RuleEvaluator:
    """
    Evaluates JSONB conditions against a booking context.
    Follows Catala's default logic: base rule applies unless
    a higher-priority exception overrides it.
    """

    OPERATORS = {
        "==": lambda a, b: a == b,
        "!=": lambda a, b: a != b,
        ">":  lambda a, b: a > b,
        ">=": lambda a, b: a >= b,
        "<":  lambda a, b: a < b,
        "<=": lambda a, b: a <= b,
        "in": lambda a, b: a in b,
        "not_in": lambda a, b: a not in b,
        "between": lambda a, b: b[0] <= a <= b[1],
    }

    def evaluate(self, conditions: dict, context: BookingContext) -> bool:
        if not conditions or not conditions.get("rules"):
            return True  # Empty conditions = always matches

        operator = conditions.get("operator", "AND")
        rules = conditions.get("rules", [])
        results = []

        for rule in rules:
            if "operator" in rule:
                # Nested group — recurse
                results.append(self.evaluate(rule, context))
            else:
                field_value = getattr(context, rule["field"], None)
                if field_value is None:
                    results.append(False)
                    continue
                op_fn = self.OPERATORS[rule["op"]]
                results.append(op_fn(field_value, rule["value"]))

        if operator == "AND":
            return all(results)
        elif operator == "OR":
            return any(results)
        return False
```

### Tax Calculation Types

```python
def calculate_tax_amount(
    rate: TaxRate,
    context: BookingContext,
    accumulated_taxes: dict[str, Decimal]
) -> Decimal:
    """Calculate tax amount based on rate type and base."""

    # Determine tax base
    base = context.nightly_rate * context.nights  # default: base_amount
    for tax_key in rate.base_includes:
        if tax_key != "base_amount" and tax_key in accumulated_taxes:
            base += accumulated_taxes[tax_key]  # compound/cascading

    match rate.rate_type:
        case "percentage":
            return base * rate.rate_value

        case "flat":
            # Flat per-night or per-person-per-night
            multiplier = context.nights
            if rate.tax_category.level_2.endswith("per_person_per_night"):
                multiplier *= context.number_of_guests
            return rate.rate_value * multiplier

        case "tiered":
            return calculate_tiered(
                context.nightly_rate,
                rate.tiers,
                rate.tier_type,
                context.nights,
                context.number_of_guests,
            )

def calculate_tiered(
    nightly_rate: Decimal,
    tiers: list[dict],
    tier_type: str,
    nights: int,
    guests: int = 1,
) -> Decimal:
    """
    OpenFisca-inspired scale calculation.

    tier_type:
      'single_amount' — returns the flat amount for the matching bracket (Tokyo style)
      'threshold'     — rate changes entirely above threshold (India GST style)
      'marginal_rate' — different rate per bracket (income tax style)
    """
    match tier_type:
        case "single_amount":
            # Tokyo: JPY 0/100/200 based on which bracket the nightly rate falls in
            for tier in tiers:
                min_val = tier.get("min", 0)
                max_val = tier.get("max")
                if max_val is None or nightly_rate < max_val:
                    if nightly_rate >= min_val:
                        return Decimal(str(tier["value"])) * nights
            return Decimal("0")

        case "threshold":
            # India GST: 12% below 7500, 18% above 7500
            for tier in reversed(tiers):
                if nightly_rate >= tier.get("min", 0):
                    return nightly_rate * nights * Decimal(str(tier["rate"]))
            return Decimal("0")

        case "marginal_rate":
            # Progressive: different rates for different portions
            total = Decimal("0")
            remaining = nightly_rate
            for tier in tiers:
                bracket_size = Decimal(str(tier.get("max", float("inf")))) - Decimal(str(tier.get("min", 0)))
                taxable = min(remaining, bracket_size)
                total += taxable * Decimal(str(tier["rate"]))
                remaining -= taxable
                if remaining <= 0:
                    break
            return total * nights
```

---

## 10. API Design

### Design Principles

- **REST** for all endpoints (industry standard for tax APIs)
- **JSON** request/response bodies
- **API versioning** via URL path (`/v1/`)
- **API keys** for authentication
- **Cursor-based pagination** for list endpoints
- **Filtering** via query parameters
- No rate limiting in v1

### Endpoints

#### Tax Calculation

```
POST /v1/tax/calculate
POST /v1/tax/calculate/batch
```

**Single calculation request:**
```json
{
  "jurisdiction_code": "US-NY-NYC",
  "stay_date": "2026-06-15",
  "checkout_date": "2026-06-18",
  "nightly_rate": 250.00,
  "currency": "USD",
  "property_type": "hotel",
  "star_rating": 4,
  "guest_type": "standard",
  "nights": 3,
  "number_of_guests": 2
}
```

**Response:**
```json
{
  "calculation_id": "calc_abc123",
  "jurisdiction": {
    "code": "US-NY-NYC",
    "name": "New York City",
    "path": "US.NY.NYC"
  },
  "input": {
    "nightly_rate": 250.00,
    "nights": 3,
    "subtotal": 750.00,
    "currency": "USD"
  },
  "tax_breakdown": {
    "components": [
      {
        "name": "New York State Sales Tax",
        "category_code": "sales_tax",
        "jurisdiction_code": "US-NY",
        "jurisdiction_level": "state",
        "rate": 0.04,
        "rate_type": "percentage",
        "taxable_amount": 750.00,
        "tax_amount": 30.00,
        "legal_reference": "NY Tax Law §1105(e)",
        "authority": "New York State Department of Taxation and Finance"
      },
      {
        "name": "NYC Local Sales Tax",
        "category_code": "sales_tax",
        "jurisdiction_code": "US-NY-NYC",
        "jurisdiction_level": "city",
        "rate": 0.045,
        "rate_type": "percentage",
        "taxable_amount": 750.00,
        "tax_amount": 33.75,
        "legal_reference": "NYC Admin Code §11-2002",
        "authority": "NYC Department of Finance"
      },
      {
        "name": "MCTD Surcharge",
        "category_code": "district_pct",
        "jurisdiction_code": "US-NY-MCTD",
        "jurisdiction_level": "special_district",
        "rate": 0.00375,
        "rate_type": "percentage",
        "taxable_amount": 750.00,
        "tax_amount": 2.81,
        "legal_reference": "NY Tax Law §1109(a)",
        "authority": "MTA"
      },
      {
        "name": "NYC Hotel Room Occupancy Tax",
        "category_code": "occ_pct",
        "jurisdiction_code": "US-NY-NYC",
        "jurisdiction_level": "city",
        "rate": 0.05875,
        "rate_type": "percentage",
        "taxable_amount": 750.00,
        "tax_amount": 44.06,
        "legal_reference": "NYC Admin Code §11-2502",
        "authority": "NYC Department of Finance"
      },
      {
        "name": "NYC Hotel Unit Fee",
        "category_code": "occ_flat_night",
        "jurisdiction_code": "US-NY-NYC",
        "jurisdiction_level": "city",
        "rate": 1.50,
        "rate_type": "flat_per_night",
        "taxable_amount": null,
        "tax_amount": 4.50,
        "legal_reference": "NYC Admin Code §11-2502(a)",
        "authority": "NYC Department of Finance"
      }
    ],
    "total_tax": 115.12,
    "effective_rate": 0.1535,
    "currency": "USD"
  },
  "total_with_tax": 865.12,
  "rules_applied": [
    {"rule_id": 456, "name": "Room rate > $40 threshold met", "result": "applied"}
  ],
  "calculated_at": "2026-03-12T10:30:00Z",
  "data_version": "2026-01-01"
}
```

#### Jurisdiction Management

```
GET    /v1/jurisdictions                          -- List (filterable by country, type, status)
GET    /v1/jurisdictions/:code                    -- Get one with full details
GET    /v1/jurisdictions/:code/children           -- Direct children
GET    /v1/jurisdictions/:code/ancestors          -- Ancestor chain to root
GET    /v1/jurisdictions/:code/tree               -- Full subtree
POST   /v1/jurisdictions                          -- Create one
POST   /v1/jurisdictions/bulk                     -- Bulk create (used by AI workflow)
PUT    /v1/jurisdictions/:code                    -- Update
GET    /v1/jurisdictions/resolve?lat=...&lng=...  -- Resolve by coordinates (PostGIS)
GET    /v1/jurisdictions/search?q=...             -- Fuzzy text search (pg_trgm)
```

**AI integration endpoint — suggest sub-jurisdictions:**
```
POST /v1/jurisdictions/:code/suggest-children
```
Triggers the external AI workflow to generate sub-jurisdictions. The workflow calls back to `POST /v1/jurisdictions/bulk` with results as `ai_draft` status.

#### Tax Rate Management

```
GET    /v1/rates                                  -- List (filterable by jurisdiction, category, status, date)
GET    /v1/rates/:id                              -- Get one with full details
GET    /v1/rates/lookup?jurisdiction_code=...&date=...  -- Get active rates for jurisdiction+date
GET    /v1/rates/history?jurisdiction_code=...&category=...&from=...&to=...  -- Historical rates
POST   /v1/rates                                  -- Create (manual)
POST   /v1/rates/bulk                             -- Bulk create (used by AI workflow)
PUT    /v1/rates/:id                              -- Update
POST   /v1/rates/:id/approve                      -- Approve ai_draft → approved/scheduled/active
POST   /v1/rates/:id/reject                       -- Reject ai_draft → rejected
POST   /v1/rates/:id/activate                     -- Manually activate
```

#### Tax Rule Management

```
GET    /v1/rules                                  -- List (filterable)
GET    /v1/rules/:id                              -- Get one
POST   /v1/rules                                  -- Create
POST   /v1/rules/bulk                             -- Bulk create
PUT    /v1/rules/:id                              -- Update
POST   /v1/rules/:id/approve                      -- Approve
POST   /v1/rules/:id/reject                       -- Reject
```

#### Monitoring Sources

```
GET    /v1/sources                                -- List sources
GET    /v1/sources?jurisdiction_code=...           -- Sources for jurisdiction
POST   /v1/sources                                -- Add source
POST   /v1/sources/bulk                           -- Bulk add (used by AI workflow)
PUT    /v1/sources/:id                            -- Update
DELETE /v1/sources/:id                            -- Remove
```

**AI integration endpoint — suggest sources for a jurisdiction:**
```
POST /v1/sources/suggest?jurisdiction_code=...
```
Triggers external AI workflow to find government websites, legislative databases, etc.

#### Detected Changes (AI Review Queue)

```
GET    /v1/changes                                -- List detected changes (filterable by status, jurisdiction)
GET    /v1/changes/:id                            -- Get change details
POST   /v1/changes/bulk                           -- Bulk create (used by AI workflow after scraping)
POST   /v1/changes/:id/approve                    -- Approve → creates/updates tax_rate
POST   /v1/changes/:id/reject                     -- Reject
POST   /v1/changes/:id/needs-info                 -- Flag for more info
GET    /v1/changes/stats                          -- Dashboard stats (pending count, confidence distribution)
```

#### Webhooks (for AI workflow integration)

```
POST   /v1/webhooks                               -- Register webhook
GET    /v1/webhooks                               -- List webhooks
DELETE /v1/webhooks/:id                            -- Remove

Events:
- jurisdiction.created                            -- New jurisdiction added
- rate.status_changed                             -- Rate moved through lifecycle
- rate.effective_soon                             -- Scheduled rate approaching effective date
- change.detected                                 -- AI found a potential change
- change.approved                                 -- Change was approved
- source.check_due                                -- Source is due for re-scraping
```

---

## 11. External AI Workflow Integration

### Overview

The AI logic lives **outside** TaxLens in an N8N-like workflow automation system. TaxLens provides:
1. **API endpoints** the AI workflow calls to read/write data
2. **Webhook events** to trigger workflows
3. **Structured JSON contracts** for what the AI should return

### Workflow A: Suggest Sub-Jurisdictions

**Trigger:** User creates a country/state in UI → clicks "Suggest sub-jurisdictions" → backend calls `POST /v1/jurisdictions/:code/suggest-children` → fires webhook → AI workflow runs.

**AI workflow steps:**
1. Receive jurisdiction code (e.g., `JP` or `US-CA`)
2. LLM generates list of sub-jurisdictions with accommodation tax relevance
3. Return structured JSON, call `POST /v1/jurisdictions/bulk`

**Expected JSON from AI:**
```json
{
  "parent_code": "JP",
  "children": [
    {
      "code": "JP-13",
      "name": "Tokyo",
      "local_name": "東京都",
      "jurisdiction_type": "prefecture",
      "country_code": "JP",
      "subdivision_code": "JP-13",
      "timezone": "Asia/Tokyo",
      "currency_code": "JPY",
      "metadata": {"has_accommodation_tax": true, "tourism_significance": "high"}
    },
    {
      "code": "JP-26",
      "name": "Kyoto",
      "local_name": "京都府",
      "jurisdiction_type": "prefecture",
      "country_code": "JP",
      "subdivision_code": "JP-26",
      "timezone": "Asia/Tokyo",
      "currency_code": "JPY",
      "metadata": {"has_accommodation_tax": true, "tourism_significance": "high"}
    }
  ]
}
```

### Workflow B: Suggest Monitoring Sources

**Trigger:** `POST /v1/sources/suggest?jurisdiction_code=JP-13-TOKYO`

**AI workflow steps:**
1. Receive jurisdiction code
2. LLM researches government websites, tax authority pages, legislative databases
3. Return list of URLs with metadata

**Expected JSON from AI:**
```json
{
  "jurisdiction_code": "JP-13-TOKYO",
  "sources": [
    {
      "url": "https://www.tax.metro.tokyo.lg.jp/english/accommodation.html",
      "source_type": "tax_authority",
      "language": "en",
      "description": "Tokyo Metropolitan Government - Accommodation Tax page",
      "check_frequency": "7 days"
    },
    {
      "url": "https://www.tax.metro.tokyo.lg.jp/kazei/shukuhaku.html",
      "source_type": "tax_authority",
      "language": "ja",
      "description": "Tokyo Accommodation Tax - Japanese official page",
      "check_frequency": "7 days"
    }
  ]
}
```

### Workflow C: Scrape & Structure Taxes

**Trigger:** Scheduled (weekly/monthly) or via webhook `source.check_due`.

**AI workflow steps:**
1. Call `GET /v1/sources?status=active` to get list of sources due for checking
2. For each source, scrape the URL content
3. Compute content hash, compare with `last_content_hash`
4. If changed, send content to LLM for structured extraction
5. Call `POST /v1/changes/bulk` with extracted data

**Expected JSON from AI (per source):**
```json
{
  "source_id": 42,
  "jurisdiction_code": "JP-13-TOKYO",
  "content_hash": "sha256:abc123...",
  "extracted_rates": [
    {
      "change_type": "rate_change",
      "confidence": 0.95,
      "source_quote": "宿泊税の税率は、1泊の宿泊料金が1万円以上1万5千円未満の場合は100円",
      "data": {
        "tax_name": "Tokyo Accommodation Tax",
        "tax_category_code": "tier_price",
        "rate_type": "tiered",
        "tier_type": "single_amount",
        "tiers": [
          {"min": 0, "max": 10000, "value": 0},
          {"min": 10000, "max": 15000, "value": 100},
          {"min": 15000, "max": null, "value": 200}
        ],
        "currency_code": "JPY",
        "effective_date": "2002-10-01",
        "legal_reference": "Tokyo Metropolitan Ordinance No. 143, 2002",
        "authority_name": "Tokyo Metropolitan Government Bureau of Taxation"
      }
    }
  ]
}
```

### LLM Structured Output Prompt (for the AI workflow system)

```
System: You are a tax rate extraction agent specializing in accommodation/lodging
taxes. You analyze government documents and extract structured tax information.

Given the following content from {source_url} for jurisdiction {jurisdiction_name}
({jurisdiction_code}):

---
{scraped_content}
---

Extract ALL accommodation-related tax rates. For each, return:

{
  "tax_name": "Name of the tax",
  "tax_category_code": "One of: occ_pct, occ_flat_night, tourism_flat_night,
    tourism_flat_person, tourism_pct, vat_standard, vat_reduced, sales_tax,
    env_flat, env_flat_person, env_pct, district_pct, district_flat,
    municipal_pct, service_pct, tier_price, tier_class, compound_pct",
  "rate_type": "percentage | flat | tiered",
  "rate_value": <number or null if tiered>,
  "tier_type": "single_amount | threshold | marginal_rate" (if tiered),
  "tiers": [...] (if tiered),
  "currency_code": "ISO 4217",
  "effective_date": "YYYY-MM-DD or null",
  "expiry_date": "YYYY-MM-DD or null",
  "conditions": {...} (matching our condition schema),
  "exemptions": ["description of each exemption"],
  "legal_reference": "statute or ordinance citation",
  "authority_name": "issuing authority",
  "source_quote": "EXACT quote from the document",
  "confidence": 0.0-1.0
}

IMPORTANT:
- Include the exact quote from the source for each rate
- Set confidence based on how clearly the rate is stated
- If ambiguous, set confidence < 0.5
- Preserve the original language in source_quote
- Use our tax_category_code taxonomy
```

---

## 12. UI/Dashboard

### Key Views

#### 1. Jurisdiction Explorer
- Interactive world map with drill-down (country → state → city → district)
- Jurisdiction tree navigator (sidebar)
- Search with autocomplete (powered by pg_trgm)
- Jurisdiction detail page: all applicable taxes, rules, history, monitored sources
- "Suggest sub-jurisdictions" button (triggers AI workflow)

#### 2. Rate Browser
- Filterable table of all tax rates across jurisdictions
- Status filter tabs: Active | Scheduled | AI Draft | Pending Review
- Timeline view showing rate changes over time per jurisdiction
- Comparison view (compare rates across jurisdictions)
- Export to CSV

#### 3. Tax Calculator Tool
- Interactive form: enter stay details, get instant tax calculation
- Shows full component breakdown with legal references
- "What-if" mode: toggle property type, stay length, guest type to see impact
- Shareable calculation link

#### 4. Change Review Dashboard
- Queue of AI-detected changes, sorted by confidence and urgency
- Side-by-side: current active rate vs. AI-suggested change
- Source quote highlighted in context
- One-click approve/reject/request-more-info
- Batch review for multiple changes from same source

#### 5. Source Management
- List of all monitored URLs per jurisdiction
- Health status (last checked, last change detected, broken links)
- "Suggest sources" button per jurisdiction (triggers AI workflow)
- Manual add/edit/pause sources

#### 6. Analytics
- Coverage dashboard: jurisdictions covered, rates tracked, sources monitored
- Change velocity: detected changes per week by region
- AI confidence distribution
- Coverage gaps: jurisdictions with no sources or no active rates

---

## 13. Edge Case Validation Scenarios

These real-world scenarios must be correctly handled to validate the system:

### Amsterdam (NL-NH-AMS)
- 7% tourist tax on the room rate — one of the highest percentage-based in Europe
- No night cap — applies regardless of stay length
- Applies to all accommodation types including Airbnb
- **Tests:** High percentage rate, no exemption by stay length, marketplace facilitator rules

### Kyoto (JP-26-KYOTO)
- Price-tiered accommodation tax:
  - < JPY 20,000/night: JPY 200
  - JPY 20,000-49,999: JPY 500
  - ≥ JPY 50,000: JPY 1,000
- Plus 10% national consumption tax (VAT equivalent)
- **Tests:** `single_amount` tier type, multi-layer (national + city), flat fee + percentage combination, JPY currency

### Virginia (US-VA)
- State transient occupancy tax: 5.3%
- Additional local transient occupancy taxes vary by city/county (Arlington: 5.25%, Virginia Beach: 8%, Fairfax County: 6%)
- 30-day exemption threshold
- Government employee exemptions with specific documentation requirements
- **Tests:** State + varied local rates, stay length exemption, guest type exemption, sub-county variation

### Paris (FR-75056)
- 10% reduced VAT on accommodation
- *Taxe de séjour*: EUR 0.25 (1-star) to EUR 5.00 (palace) — 9 tiers by classification
- Île-de-France departmental surcharge: 10% on top of taxe de séjour
- **Tests:** VAT + flat per-night (tiered by classification) + surcharge-on-tax, EUR currency, 9-tier system

### Dubai (AE-DU)
- 5% VAT + 7% Municipality Fee + 10% Service Charge + Tourism Dirham (AED 7-20 by star rating)
- Tourism Dirham is flat per-room-per-night, tiered by hotel classification
- **Tests:** 4 overlapping taxes, cascading (municipality fee on VAT-inclusive base?), star-rating tiers, AED currency

### Rome (IT-RM)
- 10% VAT on accommodation
- *Imposta di soggiorno*: EUR 3 (1-star) to EUR 7 (5-star) per person per night
- Capped at 10 consecutive nights
- Children under 10 exempt
- **Tests:** Per-person-per-night flat fee, night cap, child age exemption, star-rating tiers

### NYC (US-NY-NYC)
- 5 overlapping tax components (state sales, city sales, MCTD, city occupancy, city flat fee)
- Flat fee of $1.50/night only applies to rooms > $40/night (threshold condition)
- 90-day exemption for extended stays
- Government exemptions
- **Tests:** Multi-component with mixed percentage + flat, price threshold condition, stay length exemption (90 days), 5+ overlapping jurisdictions

### Bali (ID-BA)
- 11% national VAT + 10% provincial hotel tax + IDR 150,000 foreign tourist levy
- Service charge (10%) — mandatory but not technically a tax
- Provincial vs national tax base disputes
- **Tests:** National + provincial + per-entry levy, service charge modeling, IDR currency, tourist-only levies

### Chicago (US-IL-CHI)
- 6+ overlapping taxes exceeding 17.5%
- Different rates for STR (home-sharing) vs. hotels
- McCormick Place tax only applies in certain geographic zones
- **Tests:** Maximum stacking, property type differentiation, geographic zone-based special district

### Balearic Islands (ES-IB)
- Sustainable Tourism Tax: EUR 1-4/night
- Varies by accommodation type AND season (high: May-Oct, low: Nov-Apr)
- Low season = 50% reduction
- Children under 16 exempt
- **Tests:** Seasonal variation, property-type tiers, percentage reduction rule, child exemption

---

## 14. Technology Stack

| Layer | Technology | Rationale |
|-------|-----------|-----------|
| **Database** | PostgreSQL 16+ | ltree, daterange, JSONB, PostGIS, exclusion constraints, pg_trgm — purpose-built for this domain |
| **Backend API** | Python 3.12+ / FastAPI | Async, strong typing with Pydantic, OpenAPI docs auto-generated |
| **Rule Engine** | Python library (embedded in FastAPI) | Co-located for low latency, Decimal for precise money math |
| **ORM / DB** | SQLAlchemy 2.0 + asyncpg | Async Postgres driver, full SQL control when needed |
| **Migrations** | Alembic | Standard for SQLAlchemy |
| **Frontend** | React + TypeScript | Map viz (Leaflet/Mapbox), data tables, complex forms |
| **AI Workflow** | External N8N-like system | Calls our REST API. Uses Claude for structured extraction |
| **Testing** | pytest + httpx | API integration tests, rule engine unit tests |
| **Deployment** | Docker + docker-compose | Simple initial deployment |

### PostgreSQL Extensions

```sql
CREATE EXTENSION IF NOT EXISTS ltree;        -- Hierarchical jurisdiction paths
CREATE EXTENSION IF NOT EXISTS postgis;      -- Geospatial boundary resolution
CREATE EXTENSION IF NOT EXISTS btree_gist;   -- Required for EXCLUDE constraints
CREATE EXTENSION IF NOT EXISTS pg_trgm;      -- Fuzzy text search for jurisdiction names
```

### No Redis

All caching is handled by PostgreSQL:
- **Connection pooling** via asyncpg/pgbouncer
- **Materialized views** for pre-computed jurisdiction trees and active rate summaries
- **Proper indexing** (partial indexes on `status = 'active'`, GiST on date ranges and ltree paths)
- **Postgres query cache** handles repeated identical queries

If performance becomes a concern at scale, caching can be added later as an optimization — not an architectural requirement.

---

## 15. Implementation Phases

### Phase 1: Foundation (Weeks 1-4)

**Goal:** Core data model, API, and basic rule engine.

- [ ] PostgreSQL schema: jurisdictions, tax_categories, tax_rates, tax_rules, audit_log
- [ ] Seed tax_categories with the full L0-L2 taxonomy
- [ ] Seed property_classifications
- [ ] FastAPI project setup with Pydantic models
- [ ] Jurisdiction CRUD API with ltree queries
- [ ] Tax rate CRUD API with temporal (daterange) support
- [ ] Tax rule CRUD API
- [ ] Basic rule engine: percentage rates, flat rates
- [ ] `POST /v1/tax/calculate` endpoint
- [ ] Seed data: US top 10 cities (NYC, Chicago, SF, Houston, LA, etc.) with complete tax breakdowns
- [ ] Run edge case validation for NYC and Virginia

### Phase 2: Rule Engine Maturity (Weeks 5-8)

**Goal:** Handle full global complexity.

- [ ] Tiered rates: single_amount (Tokyo), threshold (India), marginal_rate
- [ ] Stay length exemptions
- [ ] Property type conditions
- [ ] Guest type exemptions (government, military, children)
- [ ] Night caps (Rome 10-night cap, Lisbon 7-night cap)
- [ ] Seasonal rate variations
- [ ] Tax-on-tax (cascading) calculation with calculation_order
- [ ] Per-person-per-night multiplier
- [ ] Batch calculation endpoint
- [ ] Rate history/timeline API
- [ ] Lifecycle state machine (ai_draft → approved → scheduled → active → superseded)
- [ ] Expand coverage: all US states, EU top cities, Japan, Dubai
- [ ] Run all 10 edge case validation scenarios

### Phase 3: AI Integration & Monitoring (Weeks 9-14)

**Goal:** External AI workflow integration and source monitoring.

- [ ] Monitored sources table and CRUD API
- [ ] Detected changes table and review workflow API
- [ ] `POST /v1/jurisdictions/:code/suggest-children` webhook trigger
- [ ] `POST /v1/sources/suggest` webhook trigger
- [ ] `POST /v1/changes/bulk` for AI workflow to push detected changes
- [ ] Webhook system for outbound events
- [ ] Define and document all LLM prompt templates and expected JSON contracts
- [ ] Integration tests with mock AI responses
- [ ] Review queue workflow (approve → creates active rate, reject → marks rejected)

### Phase 4: UI (Weeks 15-20)

**Goal:** React dashboard for management and monitoring.

- [ ] Jurisdiction explorer with world map + tree view
- [ ] Rate browser with status tabs and filters
- [ ] Tax calculator tool (interactive)
- [ ] Change review dashboard (approve/reject queue)
- [ ] Source management view
- [ ] Analytics / coverage dashboard
- [ ] Audit trail viewer

### Phase 5: Production Hardening (Weeks 21-26)

**Goal:** Production-ready for enterprise consumption.

- [ ] API key management and authentication
- [ ] Comprehensive test suite (regression tests per edge case scenario)
- [ ] API documentation (auto-generated OpenAPI + guides)
- [ ] Performance optimization (materialized views, query tuning)
- [ ] PostGIS jurisdiction resolution (`GET /v1/jurisdictions/resolve`)
- [ ] Bulk import/export tools
- [ ] Error handling, validation, and defensive coding throughout
- [ ] Global coverage expansion: Latin America, Middle East, Africa, rest of Asia-Pacific

---

## 16. Open Questions

### Data Strategy
1. **Initial data sourcing:** Manual research for Phase 1 (top 10 US cities), then AI-assisted expansion. Should we license base data from any provider for bootstrapping?
2. **Coverage prioritization:** Which 50 jurisdictions should we seed first? Likely: top US cities + EU capitals + Japan/Dubai/Bali.

### Business Model
3. **Pricing model:** Per-calculation, subscription tiers, or hybrid?
4. **Open data component:** Should base rate data be open with premium API access?

### Technical Decisions
5. **PostGIS necessity:** Do we maintain our own jurisdiction boundaries, or use external geocoding for Phase 1 and add PostGIS boundaries later?
6. **AI workflow system:** Which N8N-like system? N8N itself, Temporal, or custom Python scripts for v1?
7. **Scheduled state transitions:** How do we handle `scheduled → active` transitions? Postgres cron (pg_cron), or application-level scheduler?

### AI Workflow
8. **LLM selection:** Claude (preferred for accuracy and structured output) — or should the external system be model-agnostic?
9. **Source coverage:** Estimate 5,000-10,000 government URLs globally for meaningful coverage. How to prioritize initial scraping?
10. **Confidence threshold:** Below what confidence should AI-detected changes require mandatory human review? Proposed: 0.8.

### Legal/Compliance
11. **Liability:** What happens if our rates are wrong? Insurance, indemnification clauses, or "informational only" disclaimer?
12. **Government data rights:** Any restrictions on redistributing government-published tax rates?

---

## Appendix A: Full NYC Calculation Example

**Input:** 3 nights at $250/night, 4-star hotel, standard guest

| # | Tax Component | Category Code | Authority | Rate | Type | Base | Amount |
|---|--------------|---------------|-----------|------|------|------|--------|
| 1 | NY State Sales Tax | `sales_tax` | NY State | 4.000% | percentage | $750.00 | $30.00 |
| 2 | NYC Local Sales Tax | `sales_tax` | NYC | 4.500% | percentage | $750.00 | $33.75 |
| 3 | MCTD Surcharge | `district_pct` | MTA | 0.375% | percentage | $750.00 | $2.81 |
| 4 | NYC Hotel Occupancy Tax | `occ_pct` | NYC | 5.875% | percentage | $750.00 | $44.06 |
| 5 | NYC Hotel Unit Fee | `occ_flat_night` | NYC | $1.50 | flat/night | — | $4.50 |
| | **Total Tax** | | | **~15.35%** | | | **$115.12** |

**Rules evaluated:**
- Room rate $250 > $40 threshold → Unit Fee applies ✓
- Stay length 3 < 90 days → No extended stay exemption
- Guest type "standard" → No government/military exemption
- Property type "hotel" → Standard rates apply (no STR surcharge)

## Appendix B: Competitive Positioning Matrix

| Feature | TaxLens (Target) | Avalara | Vertex | Stripe Tax |
|---------|:-:|:-:|:-:|:-:|
| US lodging tax coverage | Full | Strong | Partial | Weak |
| EU tourism tax coverage | Full | Weak | Weak | Weak |
| Asia-Pacific coverage | Full | Minimal | Partial (VAT) | Minimal |
| Component-level breakdown | Yes | Partial | Partial | No |
| Historical rate queries | Yes | No | No | No |
| Future effective dates | Yes | Limited | Limited | No |
| AI change monitoring | Yes | No | No | No |
| STR vs. hotel differentiation | Yes | Partial | No | No |
| Tax-on-tax support | Yes | Yes | Yes | Limited |
| API-first | Yes | Yes | Partial | Yes |
| Rule lifecycle (draft/active/scheduled) | Yes | No | No | No |
| Hospitality-specific | Yes | Partial | No | No |
| Open taxonomy (standards-based) | Yes | No | No | No |

## Appendix C: Key Legal/Industry References

- **LegalRuleML Core Specification v1.0** (OASIS Standard, 2021) — deontic rule modeling, defeasibility, temporal dimensions
- **OpenFisca** (openfisca.org) — parameter versioning, scale types, reform model
- **Cambridge Regulatory Genome** (regulatorygenome.org) — jurisdiction-agnostic taxonomy levels
- **Catala** (catala-lang.org) — default logic for exception handling in legal rules
- **Akoma Ntoso** (OASIS LegalDocML) — jurisdiction identification, legal reference URIs
- **US Marketplace Facilitator Laws:** ~45 states as of 2025
- **EU ViDA (VAT in the Digital Age):** Expected 2027
- **OECD Model Rules for Digital Platforms**
- **Streamlined Sales Tax (SST):** 24 US states
