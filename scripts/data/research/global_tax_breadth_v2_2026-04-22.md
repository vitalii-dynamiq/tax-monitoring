# Global Tax Breadth Pass #2 — Country-Pattern Rules Focus

**Researched:** 2026-04-22 · **Scope:** Country-level rule patterns that apply across many jurisdictions (US 91-state rule gap, Canada 20, Japan 16, etc.)

## TL;DR

**26 findings · 0 new rates · 25 new rules** plus 3 rule-engine gaps flagged for future expansion.

Rule-only pass: rates are well-covered after 4 prior files. This pass attacks the per-country rule gap identified by live prod query — biggest being the US (91 rated jurisdictions with zero rules).

## Rules added

### US state rules (5 states, 7 rules)
| State | New rule(s) |
|---|---|
| IL | Permanent-resident 30-day + nonprofit narrow state exemption |
| CA | Permanent-resident 30-day (written agreement in first 30 days) |
| FL | STR 30-day threshold |
| WA | STR 30-day threshold |
| GA | $5 hotel-motel fee 30-night exemption |

### US federal (applies to all states)
- **Federal CBA card** (GSA SmartPay) — exempt from state sales tax in all 50 states + territories

### US nonprofit (existing TX, plus IL)
- **TX**: 501(c)(3) religious/charitable/educational exempt from state (not local)
- **IL**: Narrow 501(c)(3) exemption (charities focused on poverty/disease, schools, religious)

### Canada long-term rental rules (3 cities)
- **CA-ON-TOR** (Toronto): 30+ days exempt
- **CA-ON-OTT** (Ottawa): 30+ days exempt
- **CA-QC-MTL** (Montreal): 30+ days exempt

### Germany city-specific business traveler policy
- **DE-NW** (Cologne): Business travelers exempt (unchanged — rare in DE)
- **DE-HH** (Hamburg): Business travelers NOW pay (changed Jan 1, 2023 — documented)
- **DE-BE-BER** (Berlin): Business travelers NOW pay (changed Apr 1, 2024 — documented)

### Foreign-tourist VAT exemptions
- **🇮🇱 Israel**: non-Israeli passport → 18% VAT waived on accommodation
- **🇦🇷 Argentina**: non-AR resident paying with foreign card → 21% VAT waived

### Italy / France disability exemption (widespread EU pattern)
- **IT-RM, IT-VE, IT-MI, IT-FI, FR-IDF-PAR**: Disability + 1 accompanying carer exempt

### Japan prefectural nightly-rate tiered exemptions
- **JP-13** (Tokyo): `<¥10,000/night` exempt
- **JP-27** (Osaka): `<¥5,000/night` exempt
- **JP-26** (Kyoto): no exemption (minimum ¥200 always applies)

### Amsterdam long-stay
- **NL-NH-AMS**: Stays ≥180 days exempt (Dutch residence threshold)

---

## Engine-gap flags (recorded for future work)

Three categories of rule patterns we'd like but can't fully encode today:

**1. `nonprofit_*` / federal `guest_type` values**
Needed for many US state rules. Proposal: extend `BookingContext.guest_type` with `nonprofit`, `nonprofit_religious`, `nonprofit_charitable`, `nonprofit_educational`, `federal_cba`, `federal_iba`, `federal_official`, `military`, `diplomatic`. Seeded rules will use these; will fire once BookingContext accepts.

**2. `disability` / `disability_carer` values**
Needed for the widespread EU disability + 1 carer pattern. Low-risk extension.

**3. Operator-level thresholds**
Brazil R$240k habituality, Thailand 1.8M THB, Malaysia RM500k. These aren't per-booking — they decide whether a rate applies at all to a property. **Out of rule-engine scope** — belongs on property/operator registration, not on the booking calc.

---

## Delta-checking methodology

Each rule was cross-referenced against existing prod data before inclusion:
- Ran `SELECT id FROM tax_rules WHERE jurisdiction_id=X AND name ILIKE '%keyword%'` for each candidate
- Filtered out anything already active or drafted in prior batches (`ai_research_2026-04-21`, `ai_research_global_*`, `ai_research_breadth_2026-04-22`)
- Validator constraint respected: all `conditions.field` values use BookingContext allow-list

---

## Data

- JSON: [`global_tax_breadth_v2_2026-04-22.json`](./global_tax_breadth_v2_2026-04-22.json)
- 26 findings, 25 new rules, 3 engine-gap flags.
