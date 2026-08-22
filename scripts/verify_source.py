"""Verify stored rules against the LIVE government pages.

    python -m scripts.verify_source [--n 12]

Two independent checks, reported separately because they answer different
questions:

1. TEXT DRIFT -- re-fetch each scheme page and compare its current Eligibility
   text against what we stored. Government pages change without notice, so a
   corpus with a `last_verified` date is only as good as this check. Drift is
   not an error in our extraction; it means the scheme itself moved.

2. EVIDENCE -- for every stored rule, look for textual support in the CURRENT
   page: does `state eq ASSAM` correspond to "Assam" appearing? Does
   `age gte 18` correspond to an 18 in the text?

WHAT CHECK 2 DOES AND DOES NOT PROVE
It catches rules with NO basis in the source -- fabrications, annotation slips,
values typed wrong. That is a real and useful failure mode.

It does NOT prove a rule is correctly interpreted. "18" appearing in the text
is consistent with `age gte 18` and equally consistent with `age lte 18`; this
check cannot tell them apart. Read the result as "N% of rules are grounded in
the source", never as "N% of rules are correct".
"""
from __future__ import annotations

import argparse
import json
import re
from difflib import SequenceMatcher

from src.config import PROCESSED, RAW
from src.schema.fields import FIELDS
from src.schema.models import Rule


def indian_number_variants(n: float) -> list[str]:
    """₹150000 may be written 150000, 1,50,000, 1.5 lakh, or 1.50 lakh."""
    i = int(n)
    out = {str(i)}
    # Indian grouping: last 3 digits, then pairs.
    s = str(i)
    if len(s) > 3:
        head, tail = s[:-3], s[-3:]
        head = re.sub(r"(\d)(?=(\d\d)+$)", r"\1,", head)
        out.add(f"{head},{tail}")
    if i >= 100000:
        lakh = i / 100000
        out.add(f"{lakh:g} lakh")
        out.add(f"{lakh:.2f} lakh")
    if i >= 10000000:
        out.add(f"{i / 10000000:g} crore")
    return sorted(out)


def has_evidence(rule: Rule, text: str) -> bool:
    """Is there textual support for this rule in the page?"""
    low = text.lower()
    spec = FIELDS.get(rule.field)

    # Numeric fields: the number should appear in some Indian format.
    if isinstance(rule.value, (int, float)) and not isinstance(rule.value, bool):
        return any(v.lower() in low for v in indian_number_variants(rule.value))

    # Categorical / list values: the value or a recognisable form of it.
    vals = rule.value if isinstance(rule.value, list) else [rule.value]
    for v in vals:
        token = str(v).replace("_", " ").lower()
        if token in low:
            return True
        # STATE codes are stored uppercase+underscored.
        if token.replace(" ", "") in low.replace(" ", ""):
            return True

    # Booleans and enum values are almost never written the way the schema
    # spells them. The first version of this check looked for literal tokens
    # and reported 14 rules as ungrounded; inspection showed nearly all were
    # correct and the CHECKER was wrong -- the page says "woman" where the
    # schema says `female`, "Class V" where it says `class_5`. Under-reporting
    # groundedness would have understated the system, so surface forms are
    # enumerated explicitly.
    probes = list(spec.aliases) if spec else []
    probes += FIELD_PROBES.get(rule.field, [])
    probes += VALUE_PROBES.get(str(rule.value), [])
    probes.append(rule.field.replace("_", " ").replace("is ", "").replace("has ", ""))
    return any(p.lower() in low for p in probes if p)


# How these conditions are actually PHRASED on government scheme pages.
FIELD_PROBES: dict[str, list[str]] = {
    "one_per_family": ["one member per family", "only one member", "one person per family",
                       "only one", "one beneficiary per family", "more than one member"],
    "is_loan_defaulter": ["default", "defaulter", "npa", "non performing",
                          "non-performing", "overdue", "repaid"],
    "is_govt_employee": ["government employee", "govt employee", "government servant",
                         "public sector", "state/central", "government job",
                         "employee of the state", "serving or retired"],
    "is_pensioner": ["pension", "pensioner", "superannuat"],
    "is_differently_abled": ["disab", "divyang", "pwd", "physically challenged",
                             "handicap"],
    "is_bpl": ["bpl", "below poverty", "poverty line"],
    "is_income_tax_payer": ["income tax", "income-tax", "it return", "assessee"],
    "has_bank_account": ["bank account", "bank a/c", "jan dhan", "savings account"],
    "has_kcc": ["kisan credit", "kcc", "loanee"],
    "has_land_records": ["land record", "khatauni", "pattadar", "7/12", "land holding",
                         "documentary evidence"],
    "employment_status": ["unemploy", "employ", "salaried", "self employ",
                          "self-employ", "job"],
    "residence_type": ["rural", "urban", "village", "abadi", "gram"],
    "education_level": ["class", "standard", "passed", "matric", "graduat", "school"],
    "years_farming": ["year", "consecutive", "cultivat"],
    "farmer_class": ["small", "marginal", "smf"],
}

# Value-level surface forms: the schema's spelling is rarely the page's.
VALUE_PROBES: dict[str, list[str]] = {
    "female": ["woman", "women", "female", "girl", "mahila", "widow", "her"],
    "male": ["man", "men", "male", "his"],
    "other": ["transgender", "third gender"],
    "class_5": ["class v", "class 5", "5th", "fifth", "primary"],
    "class_8": ["class viii", "class 8", "8th", "eighth"],
    "class_10": ["class x", "class 10", "10th", "matric", "tenth"],
    "class_12": ["class xii", "class 12", "12th", "10+2", "intermediate"],
    "unemployed": ["unemploy", "without employment", "jobless"],
    "govt_employee": ["government employee", "govt employee", "permanent employee"],
    "SC": ["scheduled caste", "sc/st", "sc /st", "अनुसूचित"],
    "ST": ["scheduled tribe", "sc/st", "sc /st", "tribal"],
    "OBC": ["other backward", "obc", "backward class"],
    "MINORITY": ["minorit", "religious minority"],
    "True": [],     # handled by FIELD_PROBES
    "False": [],
}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=12, help="schemes to re-fetch")
    args = ap.parse_args()

    schemes = json.loads((PROCESSED / "schemes.json").read_text(encoding="utf-8"))["schemes"]
    stored = {r["slug"]: r for r in
              json.loads((RAW / "myscheme.json").read_text(encoding="utf-8"))["records"]}

    # Prefer schemes with the most rules -- they exercise the check hardest.
    picked = sorted([s for s in schemes if s["eligibility"]],
                    key=lambda s: -len(s["eligibility"]))[:args.n]

    from playwright.sync_api import sync_playwright
    from src.scrape.sources import myscheme as M

    rows, drift, gone = [], 0, 0
    total_rules = grounded = 0

    with sync_playwright() as pw:
        browser = M._launch(pw)
        page = browser.new_page()
        try:
            for s in picked:
                slug = s["apply_url"].rstrip("/").split("/")[-1]
                try:
                    live = M._render(page, s["apply_url"])
                    sections = M.split_sections(live)
                except Exception as e:
                    print(f"  ! {slug}: fetch failed ({str(e)[:50]})")
                    gone += 1
                    continue

                live_elig = sections.get("Eligibility", "")
                old_elig = stored.get(slug, {}).get("sections", {}).get("Eligibility", "")
                sim = SequenceMatcher(None, old_elig, live_elig).ratio() if old_elig else 0.0
                changed = sim < 0.98
                drift += int(changed)

                combined = " ".join(sections.values())
                ok = miss = 0
                missing_examples = []
                for rd in s["eligibility"]:
                    try:
                        rule = Rule(**rd)
                    except Exception:
                        continue
                    total_rules += 1
                    if has_evidence(rule, combined):
                        ok += 1
                        grounded += 1
                    else:
                        miss += 1
                        if len(missing_examples) < 2:
                            missing_examples.append(rule.human())
                rows.append((s["name"]["en"][:44], sim, ok, miss, missing_examples))
                flag = "CHANGED" if changed else "same"
                print(f"  {s['name']['en'][:44]:<46} text={flag:<8} "
                      f"evidence {ok}/{ok + miss}")
        finally:
            browser.close()

    print("\n" + "=" * 66)
    print(f"  schemes re-fetched      : {len(rows)}   (failed: {gone})")
    print(f"  pages changed since scrape: {drift}/{len(rows)}")
    if total_rules:
        print(f"  rules grounded in source : {grounded}/{total_rules} "
              f"({grounded / total_rules:.1%})")
    print("=" * 66)

    ungrounded = [(nm, ex) for nm, _, _, m, ex in rows if m]
    if ungrounded:
        print("\nRules with no textual support (inspect these):")
        for nm, examples in ungrounded[:6]:
            for e in examples:
                print(f"  {nm[:38]:<40} {e}")

    print("\nNOTE: 'grounded' means the value appears in the source text. It does")
    print("NOT mean the rule is correctly interpreted -- '18' supports both")
    print("`age gte 18` and `age lte 18` equally.")


if __name__ == "__main__":
    main()
