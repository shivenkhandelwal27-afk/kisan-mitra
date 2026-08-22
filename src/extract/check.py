"""Verify the extractor setup before a long run:  python -m src.extract.check

Runs one known paragraph through the configured provider and reports exactly
what is wrong if anything is. Cheaper than discovering a bad model name 40
sections into a 253-section run.
"""
from __future__ import annotations

import os
import time

TEST = ("Small and marginal farmers holding up to 2 hectares of land are eligible. "
        "Income tax payees and serving government employees are excluded. "
        "Preference will be given to women farmers.")

EXPECT = {"farmer_class", "land_ha", "is_income_tax_payer",
          "is_govt_employee", "gender"}


def main() -> None:
    from .llm import extract, PROVIDER, MODEL

    print(f"provider : {PROVIDER}")
    print(f"model    : {MODEL}")
    if PROVIDER == "gemini":
        print(f"key set  : {'yes' if os.environ.get('GEMINI_API_KEY') else 'NO'}")
    elif PROVIDER == "anthropic":
        print(f"key set  : {'yes' if os.environ.get('ANTHROPIC_API_KEY') else 'NO'}")

    print("\nrunning one test paragraph...")
    t0 = time.time()
    try:
        rules = extract(TEST)
    except Exception as e:
        print(f"\nFAILED: {type(e).__name__}: {e}")
        return

    dt = time.time() - t0
    found = {r.field for r in rules}
    print(f"took {dt:.1f}s -> {len(rules)} rules\n")
    for r in rules:
        flag = " [NEG]" if r.negated else ("" if r.mandatory else " [PREF]")
        print(f"   {r.human()}{flag}")

    missing = EXPECT - found
    print(f"\nexpected {len(EXPECT)} fields, found {len(found & EXPECT)}")
    if missing:
        print(f"missing: {', '.join(sorted(missing))}")
    if len(found & EXPECT) >= 4:
        print("\nVERDICT: good enough to pre-fill. Run:")
        print("  python -m src.extract.prefill --limit 253")
    else:
        print("\nVERDICT: under-extracting. Try a stronger model before the full run.")
    est = dt * 253 / 60
    print(f"\nestimated full run (253 sections): ~{est:.0f} min")


if __name__ == "__main__":
    main()
