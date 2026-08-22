"""End-to-end demo:  python -m src.match.demo [--profile assam|himachal|sparse]

Runs a farmer profile against the whole scheme database and prints the three
verdict buckets with human-readable reasons.

The `sparse` profile is deliberately half-empty. It exists to show that a
farmer who answers only three questions still gets useful output -- a real
farmer will not fill in twenty fields, and a system that demands them before
saying anything is useless in the field.
"""
from __future__ import annotations

import argparse

from .engine import Verdict, load_schemes, match_all

PROFILES: dict[str, dict] = {
    "assam": {
        "state": "ASSAM", "age": 34, "gender": "male",
        "social_category": "OBC", "land_ha": 1.4,
        "land_ownership": "owner", "annual_income": 90000,
        "has_kcc": True, "has_bank_account": True,
        "has_land_records": True, "years_farming": 8,
        "is_bpl": False, "is_govt_employee": False,
        "is_income_tax_payer": False, "is_pensioner": False,
        "is_loan_defaulter": False, "one_per_family": True,
        "residence_type": "rural", "crops": ["rice", "jute"],
        "livestock": ["cattle"], "employment_status": "self_employed",
    },
    "himachal": {
        "state": "HIMACHAL_PRADESH", "age": 41, "gender": "female",
        "social_category": "ST", "land_ha": 0.6,
        "land_ownership": "owner", "annual_income": 110000,
        "has_kcc": False, "has_bank_account": True,
        "is_bpl": True, "is_govt_employee": False,
        "is_pensioner": False, "is_loan_defaulter": False,
        "residence_type": "rural", "livestock": ["goat"],
        "one_per_family": True, "employment_status": "self_employed",
    },
    # Three answers only -- the realistic first-contact case.
    "sparse": {
        "state": "GUJARAT", "age": 52, "gender": "female",
    },
}


def show(results, verdict, limit, header) -> None:
    rows = [r for r in results if r.verdict is verdict][:limit]
    print(f"\n{header}  ({sum(1 for r in results if r.verdict is verdict)} total)")
    if not rows:
        print("   (none)")
        return
    for r in rows:
        pref = f"  [{len(r.preferences_met)} preference match]" if r.preferences_met else ""
        print(f"\n  * {r.scheme.name['en'][:66]}{pref}")
        if verdict is Verdict.ELIGIBLE:
            for c in r.passed[:3]:
                print(f"      + {c.explain()}")
            if r.scheme.benefit_text:
                print(f"      benefit: {r.scheme.benefit_text[:96].strip()}...")
        elif verdict is Verdict.NEED_INFO:
            print(f"      need: {', '.join(r.missing_fields)}")
            for c in r.passed[:2]:
                print(f"      + {c.explain()}")
        else:
            for c in r.failed[:2]:
                print(f"      - {c.explain()}")
        print(f"      apply: {r.scheme.apply_url}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--profile", default="assam", choices=sorted(PROFILES))
    ap.add_argument("--limit", type=int, default=4)
    args = ap.parse_args()

    profile = PROFILES[args.profile]
    schemes = load_schemes()
    results = match_all(schemes, profile)

    print("=" * 72)
    print(f"FARMER PROFILE: {args.profile}")
    print("  " + " | ".join(f"{k}={v}" for k, v in list(profile.items())[:7]))
    print(f"  ({len(profile)} fields provided, matched against {len(schemes)} schemes)")
    print("=" * 72)

    show(results, Verdict.ELIGIBLE, args.limit, "ELIGIBLE")
    show(results, Verdict.NEED_INFO, args.limit, "LIKELY ELIGIBLE - a few answers needed")
    show(results, Verdict.NOT_ELIGIBLE, 3, "NOT ELIGIBLE - and why")

    n_e = sum(1 for r in results if r.verdict is Verdict.ELIGIBLE)
    n_n = sum(1 for r in results if r.verdict is Verdict.NEED_INFO)
    n_x = sum(1 for r in results if r.verdict is Verdict.NOT_ELIGIBLE)
    print("\n" + "=" * 72)
    print(f"  {n_e} eligible | {n_n} need more info | {n_x} not eligible")
    print("=" * 72)


if __name__ == "__main__":
    main()
