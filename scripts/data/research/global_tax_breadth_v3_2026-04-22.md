# Breadth Pass #3 — Gap Hunt After 4 Prior Passes

**Researched:** 2026-04-22 · **Honest scope call:** diminishing returns reached. After 4 prior passes + this one, 5 research files on disk total ~130 findings. This pass yields **7 new rates + 10 booking-affecting rules**.

## Findings

### Italian tier-2 cities (Jubilee wave expanded)
- **Naples (IT-NA-NAP)**: NEW tax from March 1, 2025. €3-5.50/night hotels, €5 STR. **14-night cap**.
- **Bologna (IT-BO-BLQ)**: NEW tax from July 1, 2024. 10.5% capped at €7/night, **5-night cap**, under-14 exempt.
- **Turin (IT-TO-TRN)**: NEW tax from September 1, 2024. €2.30-5/night by star.

### Germany — specialty rules
- **Dresden (DE-SN-DRS)**: 6% accommodation tax with unique **under-27 educational stay exempt** rule.
- **Frankfurt (DE-HE-FRA)**: existing €2/night, add student/teacher exemption with school certificate.

### Vienna specialty
- **AT-9-VIE**: Youth hostels (`property_type == hostel`) exempt from 3.2% Ortstaxe — property-type-based rule.

### Saudi Arabia — holy cities
- **Makkah (SA-02-MKK)** / **Madinah (SA-03-MED)**: 5% municipal tax on 4-5* hotels, 2.5% on other pilgrim accommodations, effective **February 14, 2025**.

### US states — more permanent-resident rules
- **Colorado (US-CO)**: 30-day permanent resident exemption (HB20-1020)
- **Arizona (US-AZ)**: 30-day residential rental threshold
- **Pennsylvania (US-PA)**: 30-day permanent resident (61 Pa. Code Ch. 38)
- **Massachusetts (US-MA)**: 90-day excise threshold (higher than usual 30)

### Croatia
- **Split (HR-21-SPU)**: €2/night tourist tax — standard Category A coastal rate.

---

## Deferred (need BookingContext taxonomy extension)

| Jurisdiction | Rule | Needs |
|---|---|---|
| Hawaii | Military personnel exempt | `guest_type='military'` |
| Hawaii | School dormitory exempt | `property_type='school_dormitory'` or similar |
| Brussels | Underage school-group exempt | group/trip context |
| Leipzig | 5.6% rate | Jurisdiction code DE-SN-LEJ doesn't exist in DB |

## Recommendation — stop doing breadth passes

After 5 research files + breadth pass #3, **the remaining gap is taxonomy, not research**.

**Higher-leverage next step:** extend `BookingContext.guest_type` canonical values with `military`, `diplomatic`, `nonprofit`, `nonprofit_religious`, `disability`, `disability_carer`, `federal_cba`. Likely a 1-line tuple extension + updating the validator's acceptable-values set.

Doing that would unlock:
- **9 rules filtered from breadth-v2** (disability exemptions in IT-RM, IT-VE, IT-MI, IT-FI, FR-IDF-PAR + US federal CBA + TX/IL nonprofit)
- **~4 rules from this pass** (Hawaii military, Hawaii dorm, Brussels school trip, etc.)
- **Future batches** can use these values confidently

That's 13+ rules unlocked with 15 minutes of code vs. another search pass yielding similar volume at 30+ search operations.

---

## Data

- JSON: [`global_tax_breadth_v3_2026-04-22_firing.json`](./global_tax_breadth_v3_2026-04-22_firing.json) (already filtered to firing rules)
- 13 findings, 7 rates, 10 rules, 4 deferred.
