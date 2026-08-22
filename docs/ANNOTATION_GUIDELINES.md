# Annotation Guidelines — Eligibility Rule Extraction (M1)

**Version 1.0** · Lock this document before labelling begins. If a rule here
changes mid-annotation, every paragraph labelled before the change must be
re-checked, or your inter-annotator agreement score is meaningless.

## The task

Given a paragraph from a government scheme document, extract every eligibility
condition as a structured triple:

```json
{ "field": "land_ha", "op": "lte", "value": 2.0, "unit": "hectare",
  "negated": false, "mandatory": true,
  "source": { "text": "holding up to 2 hectares of cultivable land" } }
```

`field` must come from `src/schema/fields.py`. If a criterion has no matching
field, **do not invent one** — flag the paragraph as `NEEDS_FIELD` and raise it
with the team. Adding a field is a schema decision, not an annotator decision.

## Decision rules

**1. One condition per rule.** "Small and marginal farmers aged 18–40" is three
rules: `farmer_class in [small, marginal]`, `age gte 18`, `age lte 40`.
Do not use BETWEEN where two bounds read more naturally.

**2. Negation is a flag, not an operator.** "The applicant should not be a
government employee" is `is_govt_employee eq false, negated=true` — **not**
`neq true`. We track `negated` separately because negation is the highest-error
phenomenon in extraction and we report per-phenomenon F1 on it.

**3. Mandatory vs. preferential.** "Preference will be given to women farmers"
is `mandatory: false`. It affects ranking (M4), never eligibility. Words like
*preference, priority, encouraged, may be given* signal non-mandatory.

**4. Units are recorded verbatim, never converted.** Write `unit: "acre"` if the
document says acres. Conversion happens in `to_hectares()` at match time. An
annotator silently converting is an unrecoverable error, because the F1 harness
compares against the source span.

**5. Source span is mandatory.** Copy the exact substring the condition came
from. If a condition is implied across two sentences, span the shorter one and
add a `note`.

**6. Skip non-eligibility content.** Benefit amounts, application procedure,
and document lists are captured in other fields, not as eligibility rules.
Mark such paragraphs `NO_RULES` — these are **valuable negatives**; a model
that hallucinates rules from a procedure paragraph is failing, and without
labelled negatives you cannot measure that.

## Hard cases (decided — follow these)

| Source text | Correct annotation |
|---|---|
| "all landholding farmer families" | `has_land_records eq true` + `land_ownership in [owner, joint]` |
| "excluding institutional landholders" | `is_institutional_landholder eq false`, `negated=true` |
| "income tax payees in the last assessment year" (in an exclusion list) | `is_income_tax_payer eq false`, `negated=true` |
| "SC/ST farmers" | `social_category in ["SC","ST"]` |
| "farmers of Telangana state" | `state eq "TELANGANA"` |
| "5 acres" | `value: 5, unit: "acre"` — do **not** write 2.02 |
| "small and marginal farmers" | `farmer_class in ["small","marginal"]` |
| "18 to 40 years of age" | `age gte 18` **and** `age lte 40` |
| "pension of more than ₹10,000/month" (exclusion) | `pension_amount_monthly lte 10000`, `negated=true` |

## Workflow

1. Work through `data/gold/candidates.jsonl` top to bottom — do not cherry-pick,
   or your sample stops being representative.
2. For each paragraph: correct the pre-filled rules, delete wrong ones, add
   missed ones. Set `"verified": true`.
3. **Agreement check:** two annotators independently label the same 50
   paragraphs. Compute Cohen's κ with `python -m eval.agreement`. Report κ in
   the paper. Below 0.6, the disagreements are guideline gaps — resolve them
   here, then relabel.

## What counts as correct at evaluation time

A predicted rule matches gold when `field`, `op`, `negated` all match exactly
and `value` matches after unit normalisation. Partial credit is not awarded —
per-slot F1 is computed over exact triple matches, and separately as per-field
accuracy so you can see *which* fields fail.

## Known limitation of the candidate ranking (read before annotating)

`candidates.jsonl` is ordered by a **heuristic**, not a model. It reliably sinks
cost-norm tables (scores around -40) and surfaces farmer-side phrasing, but the
top of the list still contains administrative clauses — "the State shall remit
premium via NCIP" — because operational guideline PDFs are roughly 85%
implementation plumbing by volume.

This is expected and it is not a bug to fix with more regex. Deciding whether a
paragraph states a farmer-side criterion **is the M1 task**. Two consequences:

- Expect to mark a meaningful share of the top-250 as `no_rules: true`. Those
  are **valuable labelled negatives** — a model that hallucinates rules from a
  remittance clause is failing, and you can only measure that if such
  paragraphs are in the gold set. Do not skip them.
- A worthwhile Phase 2 improvement: chunk by **section heading** (target
  sections literally titled *Eligibility*, *Coverage of Farmers*, *Farmers to
  be covered*) instead of by paragraph cue-matching. That should beat the
  current heuristic and is a defensible contribution in its own right.

## Hard cases discovered during Phase 2 setup

These came out of running the baseline over real PMFBY and ATMA text. Each one
is a decision the guidelines must make, or two annotators will diverge.

**"All farmers *including* sharecroppers and tenant farmers are eligible"**
→ **No `land_ownership` rule.** "Including" is *widening*, not restricting: it
says tenure does not disqualify you. The regex baseline wrongly emits
`land_ownership in [tenant, sharecropper]`, which would exclude owner-farmers —
the opposite of what the clause means. Annotate as no ownership constraint.
Contrast with "only tenant farmers may apply", which **is** a restriction.

**Programme quotas are not individual eligibility.**
"At least 50% of beneficiaries must be Small and Marginal Farmers" constrains
the *implementing agency*, not the applicant. A farmer who is not SMF is still
eligible. Mark such sections `no_rules: true` and add a `note`.

**Assistance caps are not eligibility caps.**
"Assistance @ 50% for maximum area of 2 ha per beneficiary" limits how much
*subsidy* is paid, not who may apply. A farmer with 5 ha is eligible, but
assisted on only 2 ha. Do **not** annotate `land_ha lte 2`. If you want to
capture it, that belongs in `benefit_text`, not `eligibility`.

**Definitional clauses.**
"Farmer whose KCC loan has become sub-standard shall not be considered a Loanee
farmer" *defines a term* used by other rules. Annotate it, but set a `note`
saying it is definitional — it changes which branch of the scheme applies
rather than gating eligibility outright.

The common thread: ask **"would this sentence cause an individual farmer to be
turned away?"** If not, it is not an eligibility rule.
