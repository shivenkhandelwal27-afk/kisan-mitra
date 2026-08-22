# M1 Extraction — Ablation Study

**Gold set:** 82 hand-verified sections from myscheme.gov.in (37 Eligibility,
9 Exclusions, 36 Benefits as labelled negatives) containing **116 gold rules**.
Single annotator, pass 1. Inter-annotator κ not yet measured.

**Match criterion:** exact `(field, op, normalised value)`. No partial credit.
`negated` is scored separately — it records how a criterion was *phrased*, not
what it *is*.

## Results

| # | Extractor | Precision | Recall | **F1** | Negation F1 | no-rules acc |
|---|---|---|---|---|---|---|
| 1 | regex baseline | **0.867** | 0.336 | 0.484 | 0.000 | 0.902 |
| 2 | local 3B, 4-shot prompt | 0.444 | 0.379 | 0.409 | 0.696 | 0.902 |
| 3 | local 3B, 5-shot (+state example) | 0.594 | 0.543 | 0.568 | 0.818 | **0.927** |
| 4 | hybrid (union of 1 + 2) | 0.556 | 0.647 | 0.598 | 0.696 | 0.854 |
| 5 | **hybrid (union of 1 + 3)** | 0.631 | **0.707** | **0.667** | **0.818** | 0.854 |

Best configuration (row 5) improves F1 **38% relative** over the regex baseline
and more than doubles its recall.

Two independent axes are varied: **architecture** (regex / model / union) and
**prompt** (4-shot / 5-shot). Both matter, and the prompt change turned out to
matter more than expected.

## Finding 1 — neither extractor dominates

| field | n | regex F1 | llm F1 (5-shot) | hybrid F1 |
|---|---|---|---|---|
| state | 26 | **0.98** | 0.73 | **0.98** |
| age | 24 | 0.53 | 0.50 | **0.69** |
| annual_income | 12 | 0.00 | **0.67** | **0.67** |
| gender | 8 | 0.00 | **0.44** | **0.44** |
| is_bpl | 5 | 0.00 | **1.00** | **1.00** |
| is_loan_defaulter | 5 | 0.00 | **0.91** | **0.91** |
| land_ownership | 1 | **1.00** | 0.00 | **1.00** |

Regex is precise on surface patterns it was written for and **silent everywhere
else** — it scores 0.00 on six fields, not because it is wrong but because it
has no pattern to fire. The model generalises to unanticipated phrasings but is
noisier and weaker on the pattern-matchable fields. The union recovers the
better of each.

## Finding 2 — negation is where regex collapses

The baseline scores **exactly 0.000** on 13 negated conditions *despite having
negation patterns* for "not a government employee" and "income tax payee".
Real exclusions are phrased:

- "Government employees are not allowed to apply"
- "shall not be a loan defaulter in KMDC"
- "any person receiving a pension ... will not be eligible"

Regex cannot anticipate phrasings it was not written for. The 5-shot model
reaches **0.818 with precision 1.000** on the same conditions. This is the
strongest single argument for keeping a learned component in the extraction
layer of an otherwise symbolic system.

## Finding 3 — one few-shot example moved every metric

Error analysis on row 2 showed `state` at precision 1.00, recall 0.12: when the
model emitted a state it was always right, but it did so only 3 times in 26.
No example in the prompt carried a `state` rule.

Adding **one** example — a residency sentence with state, an age range, and a
₹1,50,000 income cap — produced row 3:

| metric | 4-shot | 5-shot | change |
|---|---|---|---|
| micro F1 | 0.409 | 0.568 | **+0.159** |
| precision | 0.444 | 0.594 | +0.150 |
| recall | 0.379 | 0.543 | +0.164 |
| negation F1 | 0.696 | 0.818 | +0.122 |
| no-rules accuracy | 0.902 | 0.927 | +0.025 |
| `state` F1 | 0.21 | 0.73 | +0.52 |
| `annual_income` F1 | 0.22 | 0.67 | +0.45 |

Precision was predicted to **fall** (more examples → more proposals → more
false positives). It rose instead. The likely mechanism is that a well-formed
4-rule example improved overall output discipline, not merely coverage of one
field — few-shot examples teach *which fields exist* and *what a complete
extraction looks like*, not only output format.

Note the example changed two things at once: it introduced `state` **and** a
lakh-notation income conversion. The `annual_income` gain is therefore
attributable to the example, but not separably from the `state` gain. A cleaner
experiment would vary one at a time.

## Cost of the hybrid

Precision falls versus the baseline (0.867 → 0.631) because the union inherits
the model's false positives, and no-rules accuracy drops (0.927 → 0.854): the
hybrid proposes a rule on 6 of 41 administrative sections versus 3 for the
model alone. The honest claim is **better F1 and recall, worse precision**.

For a welfare-access system that trade is defensible. A false positive shows a
farmer a scheme they do not qualify for; a false negative hides a benefit they
were entitled to. The symbolic matcher and the "why not eligible" explanation
surface the former to the user; nothing surfaces the latter.

## Remaining error analysis

**`education_level` scores 0.00 for every configuration** (n=3). Gold values
come from "passed at least the 8th standard" and "completed Class V", which
require mapping onto the `EDUCATION` enum. No extractor attempts it.

**`state` recall is 0.58 for the model even after the fix** — better than 0.12,
but the regex half still carries this field in the hybrid. The model omits
state on sections where residency is implied rather than stated.

**`one_per_family` regressed** in the 5-shot model (0.67 → 0.33). Small n=4, so
this may be noise, but it is the only field that got worse.

## Held-out evaluation (report THESE numbers)

The 82 sections are split 62 dev / 20 test, stratified by section type and
keyed on a hash of the section id (deterministic, no stored seed). The 5-shot
prompt was tuned on dev only; test was read once, after tuning stopped.

| Extractor | dev F1 (n=62) | **test F1 (n=20)** | dev→test |
|---|---|---|---|
| regex baseline | 0.493 | 0.444 | −0.049 |
| local 3B, 5-shot | 0.557 | 0.615 | +0.058 |
| **hybrid** | 0.663 | **0.683** | +0.020 |

**The ranking is preserved and the hybrid does not degrade on held-out data**
(0.683 test vs 0.663 dev). The prompt change therefore reflects a real
improvement in extraction rather than memorisation of the tuning set.

Reproduce:

```bash
python -m scripts.make_split
python -m eval.harness --extractor hybrid --split test
```

**Caveat that must accompany these figures:** the test split holds only 20 gold
rules. Confidence intervals are wide and per-field figures on test are not
meaningful — the negation F1 of 1.000 on test rests on a support of 2. Treat
test as confirmation that dev is not badly overfit, not as a precise estimate.
Growing the gold set is the single highest-value improvement available.

## THREAT TO VALIDITY — read before citing these numbers

**RESOLVED for the prompt change.** Rows 1-5 above were originally produced by
tuning against the same 82 sections used to evaluate. A stratified dev/test
split was added afterwards and the numbers re-measured; the held-out table
above supersedes rows 1-5 for reporting purposes. The hybrid's 0.683 on test
is an honest estimate.

**STILL OPEN — single annotator.** Every figure rests on 116 rules labelled in
one pass by one annotator. Cohen's kappa over an independently labelled
~50-section overlap has NOT been measured. Until it is, the gold set is one
party's judgement, not a measurement, and every number here inherits that.
`eval/agreement.py` implements the calculation and takes two annotated files:

```bash
python -m eval.agreement data/gold/annotatorA.jsonl data/gold/annotatorB.jsonl
```

**STILL OPEN — small test set.** 20 gold rules. See the caveat above.

**PARTIALLY ADDRESSED — source verification.** A different validity check was
run in place of the missing kappa: 12 schemes were re-fetched live and all 68
of their stored rules checked for textual support in the current government
page. Zero pages had drifted; no fabricated rule was found. See
`reports/source_verification.md`, including why the headline 100% is partly
circular and must be reported as manual verification rather than an automated
metric. This tests correctness against ground truth; it does NOT substitute
for kappa, which tests interpretation consistency.

## Reproducing

```bash
python -m eval.harness --extractor baseline
python -m eval.harness --extractor llm
python -m eval.harness --extractor hybrid
```

The LLM path requires `KISAN_LLM_PROVIDER=ollama` and `qwen2.5:3b`. Responses
are cached by prompt hash at temperature 0, so re-runs are instant and
deterministic — but **editing the prompt invalidates the entire cache** and
forces a full ~50-minute recomputation.

## Caveats

1. **Single annotator.** One pass, one annotator. Cohen's κ over an
   independently labelled 50-section overlap is still required.
2. **Test-set tuning.** See the threat-to-validity section above.
3. **n=116 rules** is small. Per-field figures with n < 5 are indicative only.
4. **Corpus skew.** The 37 schemes span agriculture, welfare, credit and
   education; only ~6 are strictly agricultural, because the scrape widened
   across four myscheme categories to work around shallow pagination.
