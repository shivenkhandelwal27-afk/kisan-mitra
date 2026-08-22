"""Assign a dev/test split to the gold set:  python -m scripts.make_split

WHY THIS EXISTS
The 5-shot prompt was written after inspecting errors on all 82 gold sections,
then evaluated on those same 82. That is fitting to the test set, and it makes
the reported F1 an optimistic estimate rather than an honest one.

From here on, TEST is never looked at while changing a prompt, a regex, or the
field vocabulary. Only the final number is read from it.

The split is:
  * deterministic  -- keyed on a hash of the section id, so it is identical on
                      every machine and every re-run, with no stored seed
  * stratified     -- Eligibility / Exclusions / Benefits appear in the same
                      proportion in both halves, so TEST is not accidentally
                      all Benefits (which carry no rules and would flatter any
                      extractor)
"""
from __future__ import annotations

import hashlib
import json
from collections import defaultdict

from src.config import GOLD

TEST_FRACTION = 0.25


def bucket(section_id: str) -> float:
    """Stable 0..1 value for an id. No RNG, no seed to lose."""
    h = hashlib.sha256(section_id.encode()).hexdigest()[:8]
    return int(h, 16) / 0xFFFFFFFF


def main() -> None:
    path = GOLD / "candidates.jsonl"
    rows = [json.loads(l) for l in open(path, encoding="utf-8")]

    # Stratify within each section type.
    by_type: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        if r.get("verified"):
            by_type[r.get("section", "other")].append(r)

    counts: dict[str, dict[str, int]] = {}
    for sect, group in by_type.items():
        group.sort(key=lambda r: bucket(r["id"]))
        n_test = max(1, round(len(group) * TEST_FRACTION))
        for i, r in enumerate(group):
            r["split"] = "test" if i < n_test else "dev"
        counts[sect] = {"dev": len(group) - n_test, "test": n_test}

    tmp = path.with_suffix(".jsonl.tmp")
    with tmp.open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    tmp.replace(path)

    dev = sum(c["dev"] for c in counts.values())
    test = sum(c["test"] for c in counts.values())
    n_rules = {s: sum(len(r.get("rules", [])) for r in by_type[s]) for s in by_type}

    print("stratified split written\n")
    print(f"  {'section':<14} {'dev':>5} {'test':>5} {'rules':>6}")
    for sect, c in sorted(counts.items()):
        print(f"  {sect:<14} {c['dev']:>5} {c['test']:>5} {n_rules[sect]:>6}")
    print(f"  {'TOTAL':<14} {dev:>5} {test:>5}")

    test_rules = sum(len(r.get("rules", [])) for g in by_type.values()
                     for r in g if r["split"] == "test")
    print(f"\n  gold rules in test: {test_rules}")
    if test_rules < 25:
        print("  NOTE: a test set this small gives wide confidence intervals.")
        print("        Report it as indicative, and grow the gold set if you can.")
    print("\nFrom now on:")
    print("  tune on   ->  python -m eval.harness --extractor X --split dev")
    print("  report on ->  python -m eval.harness --extractor X --split test")


if __name__ == "__main__":
    main()
