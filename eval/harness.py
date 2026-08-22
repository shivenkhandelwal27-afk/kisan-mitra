"""Extraction scoring:  python -m eval.harness [--extractor baseline|llm]

Scores predicted eligibility rules against the hand-verified gold set.

A prediction counts as correct only on an EXACT match of
(field, op, normalised value). No partial credit: a rule that gets the field
right but the operator wrong would admit ineligible farmers, so scoring it as
half-correct would misrepresent the system.

Reported separately:
  * micro P/R/F1 over all rules
  * per-field F1              -> shows WHICH criteria the model cannot read
  * negation-only F1          -> the phenomenon most likely to fail
  * negation-flag agreement   -> phrasing metadata, scored apart from the
                                 condition itself (see `key` for why)
  * no-rules accuracy         -> hallucination rate on administrative text
"""
from __future__ import annotations

import argparse, json, time
from collections import defaultdict

from src.config import GOLD
from src.schema.models import Rule
from src.schema.fields import to_hectares


def _norm_value(rule: Rule):
    """Canonical value for comparison: land normalised to hectares, lists sorted."""
    v = rule.value
    if rule.field == "land_ha" and rule.unit:
        try:
            return round(to_hectares(float(v), rule.unit), 4)
        except (ValueError, TypeError):
            return v
    if isinstance(v, list):
        return tuple(sorted(map(str, v)))
    if isinstance(v, float) and v.is_integer():
        return int(v)
    return v


def key(rule: Rule) -> tuple:
    """Identity of a CONDITION, deliberately excluding `negated`.

    `negated` records how the source phrased a criterion, not what the
    criterion is: "must not be a government employee" and "must be a
    non-government person" are the same condition. Including it in the match
    key double-penalised a model that extracted the right condition with the
    wrong phrasing metadata, which measures annotation style rather than
    comprehension. Negation-flag agreement is reported separately below.
    """
    return (rule.field, rule.op.value, _norm_value(rule))


def prf(tp: int, fp: int, fn: int) -> tuple[float, float, float]:
    p = tp / (tp + fp) if tp + fp else 0.0
    r = tp / (tp + fn) if tp + fn else 0.0
    f = 2 * p * r / (p + r) if p + r else 0.0
    return p, r, f


def score(rows: list[dict], extract_fn, progress: bool = False) -> dict:
    tp = fp = fn = 0
    neg_tp = neg_fp = neg_fn = 0
    flag_match = flag_total = 0
    per_field = defaultdict(lambda: [0, 0, 0])
    norules_total = norules_clean = 0
    # A local model takes 30-60s per section, so an 82-section run is a silent
    # 40 minutes without this. Silence is indistinguishable from a hang.
    t_start = time.time()

    for i, row in enumerate(rows, 1):
        if progress and i % 5 == 0:
            done = time.time() - t_start
            eta = done / i * (len(rows) - i) / 60
            print(f"  ...{i}/{len(rows)}  ~{eta:.0f} min left", flush=True)
        gold_rules = [Rule(**r) for r in row.get("rules", [])]
        pred_rules = extract_fn(row["text"])
        gold = {key(r) for r in gold_rules}
        pred = {key(r) for r in pred_rules}
        gold_neg = {key(r): r.negated for r in gold_rules}
        pred_neg = {key(r): r.negated for r in pred_rules}

        # On conditions both sides found, did they agree the source was negated?
        for k in pred & gold:
            flag_total += 1
            flag_match += int(gold_neg[k] == pred_neg[k])

        if row.get("no_rules"):
            norules_total += 1
            norules_clean += int(not pred)          # hallucinated nothing

        for k in pred & gold:
            tp += 1
            per_field[k[0]][0] += 1
            if gold_neg[k]:
                neg_tp += 1
        for k in pred - gold:
            fp += 1
            per_field[k[0]][1] += 1
            if pred_neg[k]:
                neg_fp += 1
        for k in gold - pred:
            fn += 1
            per_field[k[0]][2] += 1
            if gold_neg[k]:
                neg_fn += 1

    p, r, f = prf(tp, fp, fn)
    np_, nr, nf = prf(neg_tp, neg_fp, neg_fn)
    return {
        "n_paragraphs": len(rows),
        "micro": {"precision": p, "recall": r, "f1": f, "tp": tp, "fp": fp, "fn": fn},
        "negation": {"precision": np_, "recall": nr, "f1": nf,
                     "support": neg_tp + neg_fn},
        "negation_flag_accuracy": (flag_match / flag_total) if flag_total else None,
        "negation_flag_n": flag_total,
        "no_rules_accuracy": (norules_clean / norules_total) if norules_total else None,
        "no_rules_n": norules_total,
        "per_field": {k: dict(zip(("precision", "recall", "f1"), prf(*v)),
                              support=v[0] + v[2])
                      for k, v in sorted(per_field.items())},
    }


def report(name: str, res: dict) -> None:
    m = res["micro"]
    print(f"\n=== {name} | {res['n_paragraphs']} paragraphs ===")
    print(f"  micro    P {m['precision']:.3f}  R {m['recall']:.3f}  F1 {m['f1']:.3f}"
          f"   (tp={m['tp']} fp={m['fp']} fn={m['fn']})")
    n = res["negation"]
    print(f"  negation P {n['precision']:.3f}  R {n['recall']:.3f}  F1 {n['f1']:.3f}"
          f"   (support={n['support']})")
    if res["negation_flag_accuracy"] is not None:
        print(f"  negation-flag agreement {res['negation_flag_accuracy']:.3f} "
              f"over {res['negation_flag_n']} matched conditions")
    if res["no_rules_accuracy"] is not None:
        print(f"  no-rules accuracy {res['no_rules_accuracy']:.3f} "
              f"over {res['no_rules_n']} administrative paragraphs")
    if res["per_field"]:
        print(f"  {'field':<28} {'P':>6} {'R':>6} {'F1':>6} {'n':>4}")
        for fld, s in sorted(res["per_field"].items(), key=lambda x: -x[1]["support"]):
            print(f"  {fld:<28} {s['precision']:>6.2f} {s['recall']:>6.2f} "
                  f"{s['f1']:>6.2f} {s['support']:>4}")


def load_gold(path, split: str = "all") -> list[dict]:
    """Verified rows, optionally restricted to one split.

    `dev` is for tuning; `test` is read only when reporting a final number.
    Rows predating the split are treated as dev so old runs still work.
    """
    rows = [json.loads(l) for l in open(path, encoding="utf-8")]
    rows = [r for r in rows if r.get("verified")]
    if split == "all":
        return rows
    return [r for r in rows if r.get("split", "dev") == split]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--extractor", default="baseline", choices=["baseline", "llm", "hybrid"])
    ap.add_argument("--gold", default=str(GOLD / "candidates.jsonl"))
    ap.add_argument("--split", default="all", choices=["all", "dev", "test"],
                    help="tune on dev; read test only for the final number")
    args = ap.parse_args()

    rows = load_gold(args.gold, args.split)
    if not rows:
        print(f"No verified rows in {args.gold}.")
        print('Set "verified": true on annotated paragraphs first, or point')
        print("--gold at data/gold/example_gold.jsonl to see the harness run.")
        return

    if args.extractor == "baseline":
        from src.extract.baseline import extract
    elif args.extractor == "hybrid":
        from src.extract.hybrid import extract
    else:
        from src.extract.llm import extract

    report(f"{args.extractor} [{args.split}]",
           score(rows, extract, progress=(args.extractor != 'baseline')))


if __name__ == "__main__":
    main()
