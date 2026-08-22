"""Inter-annotator agreement:  python -m eval.agreement a.jsonl b.jsonl

Cohen's kappa over the same paragraphs labelled independently by two people.
Report this number in your paper -- it is what tells a reader your gold set is
a measurement rather than one person's opinion.

Agreement is computed per (paragraph, rule-triple) decision: for every triple
either annotator proposed, did each of them include it? That is stricter than
agreeing on paragraph-level labels, and it is the honest thing to report,
because the disagreements it surfaces are exactly the guideline gaps you need
to fix before labelling the full set.
"""
from __future__ import annotations

import json
import sys

from src.schema.models import Rule
from eval.harness import key


def kappa(a_rows: dict, b_rows: dict) -> tuple[float, int]:
    both = sorted(set(a_rows) & set(b_rows))
    if not both:
        raise SystemExit("No overlapping paragraph ids between the two files.")

    # 2x2 contingency over every triple either annotator proposed.
    n11 = n10 = n01 = n00 = 0
    for pid in both:
        a = {key(Rule(**r)) for r in a_rows[pid].get("rules", [])}
        b = {key(Rule(**r)) for r in b_rows[pid].get("rules", [])}
        for t in a | b:
            in_a, in_b = t in a, t in b
            if in_a and in_b:
                n11 += 1
            elif in_a:
                n10 += 1
            else:
                n01 += 1
        # Triples neither annotator proposed are unobservable, so n00 is
        # approximated by paragraphs both marked as containing no rules.
        if not a and not b:
            n00 += 1

    total = n11 + n10 + n01 + n00
    po = (n11 + n00) / total
    pa_yes = (n11 + n10) / total
    pb_yes = (n11 + n01) / total
    pe = pa_yes * pb_yes + (1 - pa_yes) * (1 - pb_yes)
    k = (po - pe) / (1 - pe) if pe != 1 else 1.0
    return k, len(both)


def load(path: str) -> dict:
    out = {}
    for line in open(path, encoding="utf-8"):
        r = json.loads(line)
        if r.get("verified"):
            out[r["id"]] = r
    return out


def main() -> None:
    if len(sys.argv) != 3:
        raise SystemExit(
            "usage: python -m eval.agreement <annotatorA.jsonl> <annotatorB.jsonl>")
    k, n = kappa(load(sys.argv[1]), load(sys.argv[2]))
    verdict = ("excellent" if k > 0.8 else
               "substantial" if k > 0.6 else
               "moderate -- resolve guideline gaps before continuing" if k > 0.4 else
               "poor -- the guidelines are ambiguous, fix them and relabel")
    print(f"overlapping paragraphs : {n}")
    print(f"Cohen's kappa          : {k:.3f}  ({verdict})")


if __name__ == "__main__":
    main()
