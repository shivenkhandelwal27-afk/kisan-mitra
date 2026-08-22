"""One annotator's gold-set pass over the myscheme sections.

    python -m scripts.annotate_myscheme

Labels were written by reading each section's source text, NOT by accepting
model output -- scoring an extractor against its own predictions would make
every F1 number meaningless.

Conventions follow docs/ANNOTATION_GUIDELINES.md:
  * one condition per rule
  * negation is a FLAG (eq false, negated=true), never op "neq"
  * "preference / priority" wording -> mandatory=False
  * units recorded verbatim; acres stay acres
  * inclusive phrasing ("all categories are eligible") states NO restriction
    and therefore produces no rule
  * Benefits sections describe what you receive, not who qualifies -> no_rules
    (these are the labelled negatives the harness needs)
"""
from __future__ import annotations

import json

from src.config import GOLD

R = lambda f, o, v, **k: dict(field=f, op=o, value=v, **k)      # noqa: E731
NEG = dict(negated=True)
PREF = dict(mandatory=False)

# Eligibility sections, in queue order (E0..E36).
ELIG: dict[int, list[dict]] = {
    0: [R("state", "eq", "SIKKIM"), R("employment_status", "eq", "unemployed"),
        R("education_level", "eq", "class_5"), R("age", "gte", 18, unit="years"),
        R("age", "lte", 45, unit="years"), R("one_per_family", "eq", True),
        R("annual_income", "lte", 800000, unit="INR")],
    # "all categories ... are eligible" widens rather than restricts -> no
    # social_category rule. Only the genuine gates are labelled.
    1: [R("state", "eq", "HIMACHAL_PRADESH"),
        R("is_govt_employee", "eq", False, **NEG),
        R("annual_income", "lte", 200000, unit="INR"),
        R("gender", "eq", "female", **PREF)],
    2: [R("state", "eq", "ASSAM"), R("farmer_class", "in", ["small", "marginal"]),
        R("age", "gt", 21, unit="years"), R("years_farming", "gte", 3, unit="years"),
        R("has_kcc", "eq", True), R("has_bank_account", "eq", True),
        R("one_per_family", "eq", True),
        R("land_ownership", "in", ["tenant", "sharecropper"], **PREF),
        R("land_ha", "gte", 1, unit="acre", **PREF)],
    3: [R("state", "eq", "HIMACHAL_PRADESH"),
        R("livestock", "in", ["cattle", "buffalo"])],
    4: [],      # describes the training offered, not who qualifies
    5: [R("state", "eq", "GUJARAT"), R("social_category", "in", ["ST"]),
        R("gender", "eq", "female", **PREF), R("is_bpl", "eq", True, **PREF)],
    6: [R("residence_type", "eq", "rural")],
    7: [R("state", "eq", "GUJARAT"), R("one_per_family", "eq", True)],
    8: [R("state", "eq", "GUJARAT")],
    9: [R("state", "eq", "RAJASTHAN"), R("gender", "eq", "female")],
    10: [R("residence_type", "eq", "rural")],
    11: [],     # criteria are about habitations and population, not persons
    12: [R("social_category", "in", ["SC", "ST"]),
         R("age", "gte", 18, unit="years"),
         R("is_loan_defaulter", "eq", False, **NEG)],
    13: [R("age", "gte", 18, unit="years"), R("age", "lte", 70, unit="years"),
         R("has_bank_account", "eq", True)],
    14: [R("state", "eq", "ASSAM"), R("annual_income", "lte", 2000000, unit="INR")],
    15: [R("state", "eq", "SIKKIM"), R("is_bpl", "eq", True),
         R("age", "gte", 60, unit="years"), R("is_pensioner", "eq", False, **NEG),
         R("has_bank_account", "eq", True)],
    16: [R("state", "eq", "SIKKIM"), R("gender", "eq", "other"),
         R("is_bpl", "eq", True), R("is_pensioner", "eq", False, **NEG),
         R("has_bank_account", "eq", True)],
    17: [R("state", "eq", "NAGALAND")],
    18: [R("state", "eq", "MAHARASHTRA"), R("age", "gte", 18, unit="years"),
         R("age", "lte", 50, unit="years"),
         R("annual_income", "lte", 100000, unit="INR")],
    19: [R("state", "eq", "PUNJAB"), R("is_bpl", "eq", True),
         R("social_category", "in", ["SC"]), R("age", "gte", 18, unit="years"),
         R("age", "lte", 55, unit="years"),
         R("annual_income", "lte", 100000, unit="INR"),
         R("is_differently_abled", "eq", True, **PREF)],
    20: [R("state", "eq", "ASSAM"), R("employment_status", "eq", "govt_employee"),
         R("age", "gte", 21, unit="years"), R("age", "lte", 70, unit="years")],
    21: [],     # eligible-applicant list is occupational, not in the vocabulary
    22: [R("annual_income", "lte", 48000, unit="INR")],
    23: [R("annual_income", "lte", 100000, unit="INR")],
    24: [R("state", "eq", "KARNATAKA"), R("gender", "eq", "female"),
         R("annual_income", "lte", 150000, unit="INR"),
         R("age", "gte", 18, unit="years"), R("age", "lte", 55, unit="years"),
         R("is_loan_defaulter", "eq", False, **NEG),
         R("is_differently_abled", "eq", True, **PREF)],
    25: [R("state", "eq", "MIZORAM"), R("education_level", "eq", "class_12")],
    26: [R("state", "eq", "HARYANA"), R("age", "gte", 60, unit="years"),
         R("annual_income", "lte", 300000, unit="INR")],
    27: [R("state", "eq", "GUJARAT"), R("gender", "eq", "female"),
         R("age", "gte", 18, unit="years"), R("education_level", "eq", "class_8")],
    28: [R("social_category", "in", ["SC", "OBC"])],
    29: [R("state", "eq", "JHARKHAND"), R("age", "gte", 18, unit="years")],
    30: [R("state", "eq", "WEST_BENGAL"),
         R("annual_income", "lte", 120000, unit="INR"),
         R("age", "gte", 13, unit="years"), R("age", "lte", 19, unit="years")],
    31: [R("age", "gte", 18, unit="years"), R("age", "lte", 55, unit="years"),
         R("annual_income", "lte", 350000, unit="INR"),
         R("social_category", "in", ["MINORITY"])],
    # Family income is stated per MONTH here. annual_income is an annual field
    # and the guidelines forbid silent conversion, so this criterion is left
    # unlabelled and the row is flagged for a monthly-income field.
    32: [R("state", "eq", "WEST_BENGAL"), R("age", "gte", 25, unit="years"),
         R("age", "lte", 45, unit="years"), R("one_per_family", "eq", True)],
    33: [R("state", "eq", "KERALA"), R("annual_income", "lte", 100000, unit="INR")],
    34: [R("state", "eq", "KERALA"), R("is_bpl", "eq", True)],
    35: [R("state", "eq", "GOA"), R("gender", "eq", "female")],
    36: [R("state", "eq", "UTTARAKHAND"), R("gender", "eq", "female")],
}

NEEDS_FIELD_ELIG = {21, 32}      # real criteria the vocabulary cannot express

# Exclusions sections (X0..X8). These are negation-dense by construction.
EXCL: dict[int, list[dict]] = {
    0: [R("is_loan_defaulter", "eq", False, **NEG)],
    1: [R("residence_type", "eq", "rural", **NEG)],
    2: [],      # excludes a LAND TYPE, not a class of person
    3: [],      # "already benefited" -- scheme id not in existing_schemes yet
    4: [R("is_pensioner", "eq", False, **NEG)],
    5: [R("is_loan_defaulter", "eq", False, **NEG)],
    6: [R("is_pensioner", "eq", False, **NEG)],
    7: [R("is_govt_employee", "eq", False, **NEG)],
    8: [R("is_govt_employee", "eq", False, **NEG),
        R("is_loan_defaulter", "eq", False, **NEG)],
}
NEEDS_FIELD_EXCL = {3}


def main() -> None:
    path = GOLD / "candidates.jsonl"
    rows = [json.loads(l) for l in open(path, encoding="utf-8")]

    ms = [r for r in rows if r.get("source_type") == "myscheme"]
    elig = [r for r in ms if r["section"] == "Eligibility"]
    excl = [r for r in ms if r["section"] == "Exclusions"]
    bene = [r for r in ms if r["section"] == "Benefits"]

    def apply(subset, table, needs, label):
        n_rules = 0
        for i, row in enumerate(subset):
            rules = table.get(i, [])
            row["rules"] = rules
            row["no_rules"] = not rules
            row["verified"] = True
            row["annotator"] = "claude-pass-1"
            row["needs_field"] = i in needs
            n_rules += len(rules)
        print(f"  {label:12s} {len(subset):3d} sections, {n_rules:3d} rules")
        return n_rules

    total = 0
    total += apply(elig, ELIG, NEEDS_FIELD_ELIG, "Eligibility")
    total += apply(excl, EXCL, NEEDS_FIELD_EXCL, "Exclusions")
    # Benefits state what you receive, never who qualifies. Labelling them as
    # verified negatives is what lets the harness measure hallucination.
    for row in bene:
        row["rules"] = []
        row["no_rules"] = True
        row["verified"] = True
        row["annotator"] = "claude-pass-1"
    print(f"  {'Benefits':12s} {len(bene):3d} sections,   0 rules (labelled negatives)")

    tmp = path.with_suffix(".jsonl.tmp")
    with tmp.open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    tmp.replace(path)

    verified = sum(1 for r in rows if r.get("verified"))
    print(f"\nverified rows: {verified} / {len(rows)}   total rules: {total}")
    print("\nNext:  python -m eval.harness --extractor baseline")


if __name__ == "__main__":
    main()
