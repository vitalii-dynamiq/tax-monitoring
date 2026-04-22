"""
Read-only audit of tax_rates and tax_rules, surfacing entries likely to be
irrelevant to actual tax calculation.

Heuristics (from plan binary-rolling-stonebraker.md):
  A — Unenforceable conditions (fields not in BookingContext — rule never fires)
  B — Administrative-only rules (about collectors/registration, no calc impact)
  C — Restatements (rule says nothing the rate doesn't already say)
  D — Term/expiry rules (district lifetime metadata, not calc)
  E — Not-yet-enacted proposal leftovers
  F — Duplicate / shadowed rates (active+draft on same category overlap)
  G — Zero-value placeholders (0% without statutory-zero narrative)
  H — Orphaned rules (tax_rate_id → rejected/superseded rate)

Usage:
  # prod
  export DATABASE_URL_SYNC=$(railway run --service db printenv DATABASE_PUBLIC_URL)
  python -m scripts.audit_irrelevant_entries

  # local
  python -m scripts.audit_irrelevant_entries

Flags:
  --limit-per-category N    cap each category list in output (default 50)
  --json                    emit structured JSON instead of markdown
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections import defaultdict
from dataclasses import dataclass, field

import psycopg2
import psycopg2.extras

# --- BookingContext field allow-list ---------------------------------------
# Mirrors app/core/rule_engine.py:BookingContext. If rule_engine is extended
# with new fields/properties, update this set to avoid false positives.
BOOKING_CONTEXT_FIELDS = {
    # dataclass attributes
    "jurisdiction_code", "stay_date", "checkout_date", "nightly_rate",
    "nights", "currency", "property_type", "star_rating", "guest_type",
    "guest_age", "guest_nationality", "number_of_guests", "is_marketplace",
    "platform_type", "is_bundled",
    # computed properties (in get_field)
    "stay_length_days", "stay_month", "stay_day_of_week", "total_stay_amount",
}

# --- Keyword patterns for content-based heuristics -------------------------

ADMIN_RE = re.compile(
    r"\b(?:registration|collector(?:\s+registration)?|vat\s+registrant|"
    r"annual\s+revenue|gross\s+income|turnover|"
    r"reporting\s+requirement|filing\s+requirement|remit|remittance|"
    r"licensure|licensee|license(?:d)?\s+(?:operator|vendor|provider)|"
    r"tax\s+id\s+number|business\s+tax\s+certificate|sales\s+tax\s+permit)\b",
    re.IGNORECASE,
)

TERM_RE = re.compile(
    r"\b(?:\d+[-\s]year\s+(?:term|district|collection|authorization)|"
    r"sunset\s+clause|authorized\s+for\s+\d+\s+years?|"
    r"runs?\s+through\s+(?:approximately\s+)?\d{4}|"
    r"expected\s+to\s+run\s+through\s+\d{4}|"
    r"(?:collection|assessment)\s+term\b)",
    re.IGNORECASE,
)

PROPOSAL_RE = re.compile(
    r"\b(?:not\s+yet\s+enacted|not\s+yet\s+in\s+force|not\s+yet\s+implemented|"
    r"proposed\s+but\s+not|pending\s+enactment|fast[-\s]tracking|"
    r"awaiting\s+(?:royal\s+gazette|gazette|publication|approval)|"
    r"cabinet[-\s]approved\s+but\s+not|\bis\s+a\s+proposal\b)",
    re.IGNORECASE,
)

RESTATEMENT_RE = re.compile(
    r"^(?:\w+\s+)?(?:VAT|GST|Tourism|Hotel|Occupancy|City|Municipal|Service|Accommodation)\b.*?"
    r"(?:Rate|Applies|Applicable|Standard|on\s+Accommodation|Included\s+in|Separate\s+from)",
    re.IGNORECASE,
)

# --- Helpers ---------------------------------------------------------------


def _get_dsn() -> str:
    for var in ("DATABASE_URL_SYNC", "DATABASE_URL", "DATABASE_PUBLIC_URL"):
        v = os.environ.get(var)
        if v:
            # Normalize async driver + railway prefix
            v = v.replace("postgres://", "postgresql://", 1)
            v = v.replace("postgresql+asyncpg://", "postgresql://", 1)
            return v
    return "postgresql://taxlens:taxlens@localhost:5432/taxlens"


def _walk_conditions_fields(conditions: dict | None) -> list[str]:
    """Extract all `field` names referenced in a conditions JSONB tree."""
    if not conditions:
        return []
    fields: list[str] = []
    # Leaf form: {"field": "...", "op": "...", "value": ...}
    if "field" in conditions:
        fields.append(conditions["field"])
    # Group form: {"operator": "AND|OR", "rules": [...]}
    for rule in conditions.get("rules") or []:
        if isinstance(rule, dict):
            fields.extend(_walk_conditions_fields(rule))
    # Old/alt form seen in AI output: {"AND": [...]} or {"OR": [...]}
    for key in ("AND", "OR", "and", "or"):
        for rule in conditions.get(key) or []:
            if isinstance(rule, dict):
                fields.extend(_walk_conditions_fields(rule))
    return fields


@dataclass
class Flag:
    category: str  # "A" through "H"
    severity: str  # "high" | "med" | "low"
    entity_type: str  # "rate" | "rule"
    entity_id: int
    jurisdiction_code: str
    name: str
    reason: str
    status: str
    created_by: str | None
    extra: dict = field(default_factory=dict)


# --- Fetch data ------------------------------------------------------------


def fetch_data(dsn: str) -> dict:
    conn = psycopg2.connect(dsn)
    try:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        cur.execute("""
            SELECT j.id AS jurisdiction_id, j.code AS jurisdiction_code
            FROM jurisdictions j
        """)
        jurisdictions = {r["jurisdiction_id"]: r["jurisdiction_code"] for r in cur.fetchall()}

        cur.execute("SELECT id, code FROM tax_categories")
        categories = {r["id"]: r["code"] for r in cur.fetchall()}

        cur.execute("""
            SELECT id, jurisdiction_id, tax_category_id, rate_type, rate_value,
                   effective_start, effective_end, status, created_by, review_notes,
                   authority_name, source_url
            FROM tax_rates
            WHERE status IN ('draft', 'active')
        """)
        rates = cur.fetchall()

        cur.execute("""
            SELECT id, jurisdiction_id, tax_rate_id, rule_type, priority, name,
                   description, conditions, action, effective_start, effective_end,
                   status, created_by
            FROM tax_rules
            WHERE status IN ('draft', 'active')
        """)
        rules = cur.fetchall()

        # Also grab a dict of rate status by id for orphan detection (need
        # rejected/superseded rates too, not just active/draft).
        cur.execute("SELECT id, status, tax_category_id FROM tax_rates")
        all_rate_statuses = {r["id"]: (r["status"], r["tax_category_id"]) for r in cur.fetchall()}

        cur.close()
    finally:
        conn.close()

    return {
        "jurisdictions": jurisdictions,
        "categories": categories,
        "rates": rates,
        "rules": rules,
        "all_rate_statuses": all_rate_statuses,
    }


# --- Heuristics ------------------------------------------------------------


def flag_rules(data: dict) -> list[Flag]:
    out: list[Flag] = []
    jurisdictions = data["jurisdictions"]
    all_rate_statuses = data["all_rate_statuses"]

    for rule in data["rules"]:
        rid = rule["id"]
        jcode = jurisdictions.get(rule["jurisdiction_id"], f"j#{rule['jurisdiction_id']}")
        name = rule["name"] or ""
        desc = rule["description"] or ""
        text = f"{name}\n{desc}"

        # A — Unenforceable conditions
        fields_used = _walk_conditions_fields(rule["conditions"] or {})
        unknown = [f for f in fields_used if f and f not in BOOKING_CONTEXT_FIELDS]
        if unknown:
            out.append(Flag(
                category="A",
                severity="high",
                entity_type="rule",
                entity_id=rid,
                jurisdiction_code=jcode,
                name=name,
                reason=f"conditions reference unknown field(s): {', '.join(sorted(set(unknown)))}",
                status=rule["status"],
                created_by=rule["created_by"],
                extra={"unknown_fields": sorted(set(unknown)),
                       "rule_type": rule["rule_type"]},
            ))

        # B — Administrative-only rules
        if ADMIN_RE.search(text):
            out.append(Flag(
                category="B",
                severity="high" if rule["rule_type"] == "condition" and not rule["action"] else "med",
                entity_type="rule",
                entity_id=rid,
                jurisdiction_code=jcode,
                name=name,
                reason=f"admin/reporting language: {ADMIN_RE.search(text).group(0)!r}",
                status=rule["status"],
                created_by=rule["created_by"],
                extra={"rule_type": rule["rule_type"]},
            ))

        # C — Restatements
        if (not rule["conditions"] or rule["conditions"] == {} or rule["conditions"] == {"rules": []}) \
                and RESTATEMENT_RE.search(name):
            out.append(Flag(
                category="C",
                severity="med",
                entity_type="rule",
                entity_id=rid,
                jurisdiction_code=jcode,
                name=name,
                reason="no conditions + name restates a rate type (rule adds no gating)",
                status=rule["status"],
                created_by=rule["created_by"],
            ))

        # D — Term/expiry rules
        if TERM_RE.search(text):
            out.append(Flag(
                category="D",
                severity="med",
                entity_type="rule",
                entity_id=rid,
                jurisdiction_code=jcode,
                name=name,
                reason=f"term/expiry metadata: {TERM_RE.search(text).group(0)!r}",
                status=rule["status"],
                created_by=rule["created_by"],
            ))

        # E — Not-yet-enacted
        if PROPOSAL_RE.search(text):
            out.append(Flag(
                category="E",
                severity="high",
                entity_type="rule",
                entity_id=rid,
                jurisdiction_code=jcode,
                name=name,
                reason=f"proposal language: {PROPOSAL_RE.search(text).group(0)!r}",
                status=rule["status"],
                created_by=rule["created_by"],
            ))

        # H — Orphaned rules
        if rule["tax_rate_id"] is not None:
            parent = all_rate_statuses.get(rule["tax_rate_id"])
            if parent is None:
                out.append(Flag(
                    category="H",
                    severity="high",
                    entity_type="rule",
                    entity_id=rid,
                    jurisdiction_code=jcode,
                    name=name,
                    reason=f"tax_rate_id={rule['tax_rate_id']} does not exist",
                    status=rule["status"],
                    created_by=rule["created_by"],
                ))
            elif parent[0] in ("rejected", "superseded"):
                out.append(Flag(
                    category="H",
                    severity="med",
                    entity_type="rule",
                    entity_id=rid,
                    jurisdiction_code=jcode,
                    name=name,
                    reason=f"parent rate {rule['tax_rate_id']} is status={parent[0]}",
                    status=rule["status"],
                    created_by=rule["created_by"],
                ))

    return out


def flag_rates(data: dict) -> list[Flag]:
    out: list[Flag] = []
    jurisdictions = data["jurisdictions"]
    categories = data["categories"]

    # F — Duplicates/shadowed: group active+draft by (jurisdiction, category)
    grouped: dict[tuple, list[dict]] = defaultdict(list)
    for r in data["rates"]:
        grouped[(r["jurisdiction_id"], r["tax_category_id"])].append(r)

    for (jid, cid), group in grouped.items():
        jcode = jurisdictions.get(jid, f"j#{jid}")
        ccode = categories.get(cid, f"cat#{cid}")
        statuses = {r["status"] for r in group}
        # Active+draft both present → shadowing
        if {"active", "draft"} <= statuses:
            for r in group:
                if r["status"] == "draft":
                    active_peer = next((o["id"] for o in group if o["status"] == "active"), None)
                    out.append(Flag(
                        category="F",
                        severity="high",
                        entity_type="rate",
                        entity_id=r["id"],
                        jurisdiction_code=jcode,
                        name=f"{ccode} ({r['rate_type']})",
                        reason=(f"draft shadows existing active rate #{active_peer} for same "
                                f"(jurisdiction, category); likely re-detection"),
                        status=r["status"],
                        created_by=r["created_by"],
                    ))

        # Multiple active rates with same effective_start
        active = [r for r in group if r["status"] == "active"]
        if len(active) >= 2:
            by_start = defaultdict(list)
            for r in active:
                by_start[r["effective_start"]].append(r["id"])
            for start, ids in by_start.items():
                if len(ids) >= 2:
                    for rid in ids[1:]:
                        out.append(Flag(
                            category="F",
                            severity="med",
                            entity_type="rate",
                            entity_id=rid,
                            jurisdiction_code=jcode,
                            name=ccode,
                            reason=f"{len(ids)} active rates with same effective_start={start} (siblings: {ids})",
                            status="active",
                            created_by=None,
                        ))

    # G — Zero-value placeholders
    for r in data["rates"]:
        if r["rate_type"] in ("percentage", "flat") and r["rate_value"] is not None:
            # rate_value is a Decimal from psycopg2
            if float(r["rate_value"]) == 0.0:
                notes = r["review_notes"] or ""
                source = r["source_url"] or ""
                # Heuristic: if review_notes or source quote mentions 'zero-rate', 'exempt foreign', etc.,
                # it's intentional statutory zero-rating. Otherwise placeholder.
                is_statutory_zero = bool(re.search(
                    r"(?:zero[-\s]rate|exempt(?:ion)?|reduced to 0|0%.*foreign|no\s+tax)",
                    notes,
                    re.IGNORECASE,
                ))
                jcode = jurisdictions.get(r["jurisdiction_id"], f"j#{r['jurisdiction_id']}")
                ccode = categories.get(r["tax_category_id"], f"cat#{r['tax_category_id']}")
                out.append(Flag(
                    category="G",
                    severity="low" if is_statutory_zero else "med",
                    entity_type="rate",
                    entity_id=r["id"],
                    jurisdiction_code=jcode,
                    name=f"{ccode} = 0",
                    reason=("statutory zero-rate per notes (keep)"
                            if is_statutory_zero
                            else "rate_value=0 without statutory-zero narrative in review_notes"),
                    status=r["status"],
                    created_by=r["created_by"],
                    extra={"source_url": source},
                ))

    # E — Not-yet-enacted (on rates, check review_notes + authority_name)
    for r in data["rates"]:
        text = f"{r['review_notes'] or ''}\n{r['authority_name'] or ''}"
        if PROPOSAL_RE.search(text):
            jcode = jurisdictions.get(r["jurisdiction_id"], f"j#{r['jurisdiction_id']}")
            ccode = categories.get(r["tax_category_id"], f"cat#{r['tax_category_id']}")
            out.append(Flag(
                category="E",
                severity="high",
                entity_type="rate",
                entity_id=r["id"],
                jurisdiction_code=jcode,
                name=ccode,
                reason=f"rate metadata contains proposal language: {PROPOSAL_RE.search(text).group(0)!r}",
                status=r["status"],
                created_by=r["created_by"],
            ))

    return out


# --- Output ----------------------------------------------------------------


CATEGORY_DESCRIPTIONS = {
    "A": "Unenforceable conditions — rule can never fire",
    "B": "Administrative-only rules — about collectors/registration, no calc impact",
    "C": "Restatements — rule adds no gating over its rate",
    "D": "Term/expiry metadata — district lifetime info, not a calc rule",
    "E": "Not-yet-enacted / proposal leftovers",
    "F": "Duplicate / shadowed rates",
    "G": "Zero-value placeholders",
    "H": "Orphaned rules — parent rate missing/rejected/superseded",
}


def render_markdown(flags: list[Flag], data: dict, limit_per_category: int) -> str:
    # Aggregate multi-flag items (⚠️⚠️)
    flag_count_by_entity: dict[tuple, int] = defaultdict(int)
    for f in flags:
        flag_count_by_entity[(f.entity_type, f.entity_id)] += 1

    by_category: dict[str, list[Flag]] = defaultdict(list)
    for f in flags:
        by_category[f.category].append(f)

    severity_order = {"high": 0, "med": 1, "low": 2}
    for cat in by_category:
        by_category[cat].sort(key=lambda f: (severity_order[f.severity], f.jurisdiction_code, f.entity_id))

    total_flagged_entities = len({(f.entity_type, f.entity_id) for f in flags})
    high_sev = len({(f.entity_type, f.entity_id) for f in flags if f.severity == "high"})
    multi = [e for e, c in flag_count_by_entity.items() if c >= 2]

    lines: list[str] = []
    lines.append("## Rules/Rates Irrelevance Audit")
    lines.append("")
    lines.append(f"**Scope**: {len(data['rates'])} rates + {len(data['rules'])} rules (status IN (active, draft))")
    lines.append(f"**Flagged entities**: {total_flagged_entities} total "
                 f"({high_sev} high severity, {len(multi)} multi-category)")
    lines.append("")

    if multi:
        lines.append("### ⚠️⚠️ Multi-category flags (review first)")
        for etype, eid in sorted(multi):
            entity_flags = [f for f in flags if f.entity_type == etype and f.entity_id == eid]
            f0 = entity_flags[0]
            cats = ",".join(sorted({x.category for x in entity_flags}))
            lines.append(
                f"- {etype} #{eid} ({f0.jurisdiction_code}) [{cats}] — \"{f0.name[:80]}\" "
                f"[status={f0.status}, batch={f0.created_by}]"
            )
            for fx in entity_flags:
                lines.append(f"    - **{fx.category}**: {fx.reason}")
        lines.append("")

    for cat in sorted(by_category):
        items = by_category[cat]
        lines.append(f"### {cat}. {CATEGORY_DESCRIPTIONS[cat]} ({len(items)} items)")
        shown = items[:limit_per_category]
        for f in shown:
            lines.append(
                f"- {f.entity_type} #{f.entity_id} ({f.jurisdiction_code}) "
                f"[sev={f.severity}, status={f.status}]: \"{f.name[:80]}\" — {f.reason}"
            )
        if len(items) > limit_per_category:
            lines.append(f"  *(...and {len(items) - limit_per_category} more)*")
        lines.append("")

    # Summary table
    lines.append("### Summary counts per category")
    lines.append("")
    lines.append("| Cat | High | Med | Low | Total |")
    lines.append("|-----|------|-----|-----|-------|")
    for cat in sorted(by_category):
        hi = sum(1 for f in by_category[cat] if f.severity == "high")
        me = sum(1 for f in by_category[cat] if f.severity == "med")
        lo = sum(1 for f in by_category[cat] if f.severity == "low")
        lines.append(f"| {cat}   | {hi}    | {me}   | {lo}   | {len(by_category[cat])}    |")
    lines.append("")
    return "\n".join(lines)


def render_json(flags: list[Flag]) -> str:
    return json.dumps([
        {
            "category": f.category,
            "severity": f.severity,
            "entity_type": f.entity_type,
            "entity_id": f.entity_id,
            "jurisdiction_code": f.jurisdiction_code,
            "name": f.name,
            "reason": f.reason,
            "status": f.status,
            "created_by": f.created_by,
            "extra": f.extra,
        }
        for f in flags
    ], indent=2, default=str)


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n", 1)[0])
    p.add_argument("--limit-per-category", type=int, default=50)
    p.add_argument("--json", action="store_true")
    args = p.parse_args()

    dsn = _get_dsn()
    # Safe to print the host, not the password
    host = dsn.split("@")[1].split("/")[0] if "@" in dsn else dsn
    sys.stderr.write(f"Audit DB: {host}\n")
    data = fetch_data(dsn)
    sys.stderr.write(f"Loaded {len(data['rates'])} rates, {len(data['rules'])} rules, "
                     f"{len(data['jurisdictions'])} jurisdictions, {len(data['categories'])} categories\n")

    flags = flag_rules(data) + flag_rates(data)

    if args.json:
        print(render_json(flags))
    else:
        print(render_markdown(flags, data, args.limit_per_category))
    return 0


if __name__ == "__main__":
    sys.exit(main())
