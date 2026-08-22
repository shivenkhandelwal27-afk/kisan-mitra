"""Build the matchable scheme database:  python -m src.extract.build_schemes

Joins the scraped scheme pages (data/raw/myscheme.json) with their eligibility
rules and writes data/processed/schemes.json -- the file the matcher reads.

Rule provenance matters and is recorded per scheme. By default we prefer
HAND-VERIFIED gold rules where they exist, falling back to the extractor
elsewhere. The extractor's accuracy is measured separately in the ablation; the
matcher demo should not be silently degraded by a 0.667-F1 pipeline when
verified rules are available for the same sections.

    --extractor hybrid   ignore gold, use machine extraction throughout
                         (this is what an end-to-end automated run looks like)
"""
from __future__ import annotations

import argparse
import json
import re
from datetime import date

from ..config import RAW, PROCESSED, GOLD
from ..schema.models import Rule, Scheme, SchemeCategory

# Crude keyword routing for the category field. The scheme title is usually
# explicit about what kind of programme it is. A learned classifier would be a
# reasonable M-series addition later; it is not needed to match eligibility.
CATEGORY_HINTS: list[tuple[str, SchemeCategory]] = [
    (r"insur|bima|health|medical|chikitsa", SchemeCategory.INSURANCE),
    (r"pension|old age|samman|vridh", SchemeCategory.PENSION_WELFARE),
    (r"loan|credit|lending|subvention|swavlamban|udyogini|stand.?up",
     SchemeCategory.CREDIT_LOAN),
    (r"scholar|shiksha|student|girl|kanyashree|medhavi|education",
     SchemeCategory.TRAINING),
    (r"train|skill|kaushal|vocational", SchemeCategory.TRAINING),
    (r"irrigat|sinchai|water|drip|sprinkler", SchemeCategory.IRRIGATION),
    (r"bakri|palan|pashu|dairy|poultry|livestock|fisher|goat|cattle",
     SchemeCategory.ALLIED_ACTIVITY),
    (r"road|sadak|awas|ghar|hous|infrastructure", SchemeCategory.INFRASTRUCTURE),
    (r"market|mandi|nam\b|procure", SchemeCategory.MARKET_ACCESS),
    (r"subsid|sahay|assist|yojana|scheme", SchemeCategory.SUBSIDY_INPUT),
]


def infer_category(title: str) -> SchemeCategory:
    low = title.lower()
    for pattern, cat in CATEGORY_HINTS:
        if re.search(pattern, low):
            return cat
    return SchemeCategory.SUBSIDY_INPUT


def slugify(title: str, fallback: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
    return s[:60] or fallback


def load_gold_rules() -> dict[str, list[dict]]:
    """Map section-id -> verified rules, for sections a human has signed off."""
    path = GOLD / "candidates.jsonl"
    if not path.exists():
        return {}
    out = {}
    for line in open(path, encoding="utf-8"):
        row = json.loads(line)
        if row.get("verified") and row.get("source_type") == "myscheme":
            out[row["id"]] = row.get("rules", [])
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--extractor", default="gold",
                    choices=["gold", "hybrid", "baseline", "llm"],
                    help="'gold' prefers verified rules, falling back to hybrid")
    args = ap.parse_args()

    raw = json.loads((RAW / "myscheme.json").read_text(encoding="utf-8"))
    gold = load_gold_rules() if args.extractor == "gold" else {}

    if args.extractor in ("hybrid", "gold"):
        from .hybrid import extract
    elif args.extractor == "baseline":
        from .baseline import extract
    else:
        from .llm import extract

    import hashlib

    schemes: list[Scheme] = []
    n_gold = n_machine = 0

    for rec in raw["records"]:
        title = rec["title"]
        sections = rec["sections"]
        rules: list[Rule] = []
        provenance = set()

        for name in ("Eligibility", "Exclusions"):
            text = sections.get(name)
            if not text or len(text) < 40:
                continue
            sec_id = hashlib.sha256(text.encode()).hexdigest()[:16]
            if sec_id in gold:
                raw_rules = gold[sec_id]
                provenance.add("verified")
                n_gold += 1
                rules += [Rule(**r) for r in raw_rules]
            else:
                provenance.add("extracted")
                n_machine += 1
                rules += extract(text)

        # De-duplicate. `negated` is excluded from the key for the same reason
        # eval.harness excludes it: it records how a criterion was PHRASED,
        # not what it is. A scheme that says "rural areas are eligible" under
        # Eligibility and "urban areas are not eligible" under Exclusions
        # states ONE condition, and keeping both showed the farmer the same
        # reason twice.
        seen, uniq = set(), []
        for r in rules:
            k = (r.field, r.op, str(r.value))
            if k not in seen:
                seen.add(k)
                uniq.append(r)

        # A scheme's states come from its own extracted state rules. Absent
        # any, treat it as nationally applicable rather than silently
        # excluding it from every farmer's results.
        states = sorted({str(r.value) for r in uniq
                         if r.field == "state" and r.op.value == "eq"}) or ["ALL"]

        schemes.append(Scheme(
            id=slugify(title, rec["slug"]),
            name={"en": title},
            category=infer_category(title),
            level="state" if states != ["ALL"] else "central",
            states=states,
            benefit_text=(sections.get("Benefits") or "")[:600],
            eligibility=uniq,
            documents=[],
            apply_url=rec["url"],
            source_url=rec["url"],
            last_verified=date.today(),
            raw_eligibility_text=sections.get("Eligibility", ""),
            raw_benefit_text=(sections.get("Benefits") or "")[:600],
            gold_verified="verified" in provenance and "extracted" not in provenance,
        ))

    PROCESSED.mkdir(parents=True, exist_ok=True)
    out = PROCESSED / "schemes.json"
    out.write_text(json.dumps(
        {"generated_at": str(date.today()),
         "rule_source": args.extractor,
         "schemes": [s.model_dump(mode="json", exclude_none=True) for s in schemes]},
        ensure_ascii=False, indent=1), encoding="utf-8")

    total_rules = sum(len(s.eligibility) for s in schemes)
    fully_verified = sum(1 for s in schemes if s.gold_verified)
    print(f"wrote {out}")
    print(f"  schemes            : {len(schemes)}")
    print(f"  eligibility rules  : {total_rules} ({total_rules/max(len(schemes),1):.1f} per scheme)")
    print(f"  sections from gold : {n_gold}   from extractor: {n_machine}")
    print(f"  fully verified     : {fully_verified}/{len(schemes)} schemes")
    print(f"  schemes with 0 rules: {sum(1 for s in schemes if not s.eligibility)}")
    print("\nNext:  python -m src.match.demo")


if __name__ == "__main__":
    main()
