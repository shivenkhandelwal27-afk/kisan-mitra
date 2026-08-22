"""Prepare the second-annotator file:  python -m scripts.make_annotator_b

Cohen's kappa needs two people labelling the SAME sections INDEPENDENTLY. This
writes a copy of 50 sections with every rule stripped, so annotator B starts
from the raw text and cannot be anchored by annotator A's answers.

Anchoring is the whole risk here: showing B what A wrote would produce a high
kappa that measures agreement with a suggestion, not agreement about the text.
"""
from __future__ import annotations

import json

from src.config import GOLD

# 20, not 50. Kappa needs enough decisions to be stable, not a large sample --
# these 20 sections carry ~60 rule-level decisions between them, which is
# adequate for a project-scale reliability estimate. A wide confidence
# interval that is honestly reported beats a precise number nobody produced.
N_OVERLAP = 20


def main() -> None:
    rows = [json.loads(l) for l in open(GOLD / "candidates.jsonl", encoding="utf-8")]
    verified = [r for r in rows if r.get("verified")]
    # Take the highest-priority sections: the ones carrying actual criteria.
    with_rules = [r for r in verified if r.get("rules")]
    overlap = sorted(with_rules, key=lambda r: -len(r["rules"]))[:N_OVERLAP]

    out = GOLD / "annotator_b.jsonl"
    with out.open("w", encoding="utf-8") as f:
        for r in overlap:
            f.write(json.dumps({
                "id": r["id"],
                "section": r.get("section"),
                "doc": r.get("doc"),
                "text": r["text"],
                "source_url": r.get("source_url"),
                "rules": [],          # blank on purpose
                "no_rules": False,
                "verified": False,    # B sets this to true as they go
                "annotator": "B",
            }, ensure_ascii=False) + "\n")

    n_sec = {}
    for r in overlap:
        n_sec[r.get("section")] = n_sec.get(r.get("section"), 0) + 1
    print(f"wrote {out}  ({len(overlap)} sections, rules blanked)")
    print(f"  composition: {n_sec}")
    print("\nGive annotator B:")
    print("  1. this file")
    print("  2. docs/ANNOTATION_GUIDELINES.md")
    print("  3. NOT data/gold/candidates.jsonl -- seeing A's labels invalidates kappa")
    print("\nWhen B is done:")
    print("  python -m eval.agreement data/gold/candidates.jsonl data/gold/annotator_b.jsonl")


if __name__ == "__main__":
    main()
