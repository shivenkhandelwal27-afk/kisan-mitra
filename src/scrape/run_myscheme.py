"""Build the farmer-facing corpus:  python -m src.scrape.run_myscheme

Separate entry point from `src.scrape.run` because this one drives a headless
browser: it is slower, needs Chromium installed, and is worth running on its
own schedule. The PDF/Wikipedia scrape stays independent.

    python -m src.scrape.run_myscheme --pages 8 --schemes 60

Writes data/raw/myscheme.json. Individual pages are cached under
data/raw/_myscheme/, so re-runs cost nothing and are safe to interrupt.
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import date

from ..config import RAW, TARGET_STATES
from .sources import myscheme

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s",
                    stream=sys.stdout)
log = logging.getLogger("myscheme")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pages", type=int, default=8,
                    help="listing pages to paginate (10 schemes per page)")
    ap.add_argument("--schemes", type=int, default=60,
                    help="cap on scheme pages to render")
    args = ap.parse_args()

    records = myscheme.run(max_pages=args.pages, max_schemes=args.schemes)

    flat = []
    for rec in records:
        flat.extend(myscheme.annotatable_sections(rec))

    out = RAW / "myscheme.json"
    out.write_text(json.dumps(
        {"generated_at": str(date.today()), "states": TARGET_STATES,
         "n_schemes": len(records), "records": records, "sections": flat},
        ensure_ascii=False, indent=1), encoding="utf-8")

    with_elig = sum(1 for r in records if "Eligibility" in r["sections"])
    with_excl = sum(1 for r in records if "Exclusions" in r["sections"])

    print("\n" + "=" * 62)
    print(f"  schemes rendered        : {len(records)}")
    print(f"  with Eligibility section: {with_elig}")
    print(f"  with Exclusions section : {with_excl}   <- negation-rich")
    print(f"  annotatable sections    : {len(flat)}")
    print("=" * 62)
    if len(flat) < 150:
        print(f"  Only {len(flat)} sections. Raise --pages / --schemes for more.")
    print(f"\nwrote {out}")
    print("Next:  python -m src.extract.candidates")


if __name__ == "__main__":
    main()
