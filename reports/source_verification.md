# Source verification — are the stored rules actually in the source?

Run: `python -m scripts.verify_source --n 12`
Date: 2026-08-22 · 12 schemes re-fetched live from myscheme.gov.in · 68 rules

This is a **different** validity check from inter-annotator agreement. Kappa
asks "do two people read this text the same way?". This asks "is what we
stored actually present in the government's page?" — correctness against
ground truth rather than consistency between annotators.

## Results

| Check | Result |
|---|---|
| Schemes re-fetched successfully | 12 / 12 |
| Pages changed since our scrape | **0 / 12** |
| Rules with textual support in the live page | **68 / 68** |

**Text drift: zero.** Every Eligibility section was byte-comparable to what we
scraped. The corpus is current as of this date, which matters because
government pages change without notice and a `last_verified` field is only
worth what this check says it is.

## HOW THE 100% WAS OBTAINED — read this before citing it

The first run reported **54/68 (79.4%)**. The 14 failures were inspected by
hand. Every one turned out to be a **correct rule that the checker could not
recognise**, because the schema's spelling is not the page's wording:

| Stored rule | What the page actually says |
|---|---|
| `gender is female` | "the applicant should be a **woman**" |
| `education level is class_5` | "completed at least **Class V**" |
| `one per family is True` | "**Only one member per family** is eligible" |
| `is loan defaulter is False` | "should not have **defaulted** on any past loan" |
| `is pensioner is False` | "recipient of salary/**pension**/family pension" |

The probe list was then extended with these surface forms, and the score rose
to 68/68.

**That makes the 100% partly circular.** The checker was adjusted after seeing
which rules it failed on. The honest statement of this result is:

> All 68 rules across 12 schemes were verified as having textual support in
> the live source. 14 required manual inspection because automated matching
> could not bridge schema-to-prose vocabulary differences; all 14 were
> confirmed correct on inspection. No fabricated or unsupported rule was
> found.

That is a real and useful finding — **no hallucinated rules in the sample** —
but it is manual verification assisted by a checker, not an independent
automated metric. Do not report "100% automated verification".

## What this check cannot tell you

Groundedness is not correctness. The token "18" supports `age gte 18` and
`age lte 18` equally; this method cannot distinguish them. It detects rules
invented from nothing, not rules interpreted wrongly.

Inter-annotator agreement remains the outstanding gap for interpretation
quality, and is still unmeasured — see `reports/ablation.md`.

## Method note worth carrying into the report

This is the third time in this project that a bad-looking number turned out to
be a broken measurement rather than a broken system:

1. Extraction appeared to fail on ministry PDFs — the **corpus** contained no
   farmer eligibility, not the models.
2. Eight schemes appeared to lack Eligibility sections — a **render race**
   captured pages before the section loaded.
3. 14 rules appeared unsupported — the **checker's vocabulary** was too
   literal.

Each looked like a quality problem and was an instrumentation problem. When a
metric reports something bad, verify the metric before acting on it.
