"""Pre-fill annotation labels:  python -m src.extract.prefill [--limit N]

Runs the M1 extractor over data/gold/candidates.jsonl and writes its proposed
rules into each row. You then CORRECT those rules rather than writing them from
scratch, which is the difference between roughly 15 hours of annotation and 4.

Nothing here sets "verified". A pre-filled row is a machine guess; only a human
setting verified=true turns it into gold. Keeping that boundary strict is what
stops the evaluation from scoring the model against its own output.

Safe to interrupt and re-run: model responses are cached by prompt hash AND
rows are flushed to disk as they complete, so a killed run resumes instead of
starting over.
"""
from __future__ import annotations

import argparse
import json
import time

from ..config import GOLD

# A provider that has started refusing (quota exhausted, key revoked, service
# down) will refuse every subsequent call too. An earlier version of this
# script had no such guard and ground through ~170 consecutive failures over
# nine hours before it was killed. Stop early and tell the user why.
MAX_CONSECUTIVE_FAILURES = 6
FLUSH_EVERY = 5


def _flush(path, rows) -> None:
    """Write all rows atomically-ish, so a kill mid-write cannot truncate."""
    tmp = path.with_suffix(".jsonl.tmp")
    with tmp.open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    tmp.replace(path)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=250,
                    help="how many top-priority candidates to pre-fill")
    ap.add_argument("--overwrite", action="store_true",
                    help="re-run rows that already carry pre-filled rules")
    args = ap.parse_args()

    path = GOLD / "candidates.jsonl"
    rows = [json.loads(l) for l in open(path, encoding="utf-8")]

    from .llm import extract, PROVIDER, MODEL
    target = min(args.limit, len(rows))
    print(f"provider={PROVIDER} model={MODEL}")
    print(f"pre-filling top {target} of {len(rows)} candidates\n")

    done = skipped = failed = 0
    consecutive = 0
    last_error = ""
    t0 = time.time()
    aborted = False

    for i, row in enumerate(rows[:target]):
        if row.get("verified"):
            skipped += 1
            continue                       # never overwrite human work
        if row.get("rules") and not args.overwrite:
            skipped += 1
            continue

        try:
            rules = extract(row["text"])
            consecutive = 0
        except Exception as e:
            failed += 1
            consecutive += 1
            last_error = f"{type(e).__name__}: {e}"
            print(f"  [{i+1}] FAILED: {last_error[:100]}")
            if consecutive >= MAX_CONSECUTIVE_FAILURES:
                aborted = True
                break
            continue

        row["rules"] = [r.model_dump(mode="json", exclude_none=True) for r in rules]
        row["no_rules"] = not rules
        row["prefilled_by"] = f"{PROVIDER}:{MODEL}"
        done += 1

        # Flush as we go. Everything completed so far survives a kill.
        if done % FLUSH_EVERY == 0:
            _flush(path, rows)

        if done % 10 == 0:
            elapsed = time.time() - t0
            rate = done / elapsed if elapsed > 0 else 0.0
            eta = f"~{(target - i - 1) / rate / 60:.0f} min left" if rate > 0 else "ETA unknown"
            print(f"  {i+1:>4}/{target}  {rate*60:.1f}/min  {eta}")

    _flush(path, rows)

    n_rules = sum(len(r.get("rules", [])) for r in rows[:target])
    n_empty = sum(1 for r in rows[:target] if r.get("no_rules"))
    mins = (time.time() - t0) / 60

    if aborted:
        print(f"\nABORTED after {consecutive} consecutive failures.")
        print(f"  last error: {last_error[:300]}")
        print(f"  {done} rows completed and saved before stopping.")
        print("\nLikely causes: free-tier quota exhausted for the day, network")
        print("down, or the model id is no longer served. Re-running resumes")
        print("from where this stopped -- completed rows are cached.")
        return

    print(f"\npre-filled {done} rows in {mins:.1f} min "
          f"(skipped {skipped}, failed {failed})")
    print(f"  proposed rules      : {n_rules}")
    print(f"  marked as no-rules  : {n_empty}")
    if done and n_rules / done < 0.3:
        print("\n  WARNING: fewer than 0.3 rules per section. That usually means")
        print("  the SOURCE documents do not state farmer eligibility, not that")
        print("  the model is weak. Check what corpus these sections came from.")
    print(f"\nNext: open {path} and correct the rules, setting \"verified\": true")
    print("as you go. Then score the baseline against your gold:")
    print("  python -m eval.harness --extractor baseline")


if __name__ == "__main__":
    main()
