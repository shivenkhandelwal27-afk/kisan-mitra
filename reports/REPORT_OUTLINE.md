# Report outline — Kisan Mitra

Every number below is real and comes from a file in this repo. Nothing here is
a placeholder you need to compute. `[WRITE]` marks prose only you can write.

Target length for a semester AIML project: 15–25 pages.

---

## 1. Abstract  `[WRITE]` (200 words, write last)

Cover in this order: the access problem → what the system does → the
neuro-symbolic design → the headline number → the honest limitation.

Headline: **hybrid extraction reaches F1 0.683 on held-out data, a 54% relative
improvement over a regex baseline (0.444)**, and the matcher converts extracted
rules into explained eligibility verdicts across 37 schemes.

---

## 2. Introduction

**2.1 Problem**  `[WRITE]` — restate the brief in your own words. The core
point: eligibility information exists but is scattered, written in legal
register, and rarely in the reader's language.

**2.2 Why this is hard.** Use these concrete examples from your own corpus:

- Criteria are stated negatively: *"any person receiving a pension … will not
  be eligible"*
- Units are mixed within a document: acres and hectares in adjacent clauses
- Preference is not requirement: *"preference will be given to women farmers"*
  does not disqualify men
- Schema-to-prose gap: the page says *"a woman"*, *"Class V"*; a database needs
  `gender=female`, `education_level=class_5`

**2.3 Contributions.** Four, all defensible:

1. A hand-verified dataset of **116 eligibility rules** over 82 sections from
   37 government schemes, with a 33-field controlled vocabulary
2. A three-way extraction ablation showing regex and a 3B model fail in
   **opposite directions**, and their union beats both
3. A symbolic matcher producing three verdicts with per-rule explanations
4. A working bilingual interface (English/Hindi)

---

## 3. Related Work  `[WRITE]`

You must fill this in — I have not surveyed the literature and you should not
cite work you have not read. Four areas to search:

- Information extraction from regulatory/legal text
- Neuro-symbolic systems (neural perception + symbolic reasoning)
- Rule-based eligibility / expert systems for benefits access
- Indic NLP (AI4Bharat: IndicBERT, IndicTrans2)

One paragraph each, ending with how your work differs.

---

## 4. System Architecture

Reproduce the diagram from `README.md`. The argument to make explicitly:

> Neural components *understand*; a symbolic engine *decides*. The eligibility
> decision is deterministic and auditable by design, because a farmer denied a
> benefit deserves a reason a human can inspect, and "the model said so" is not
> one.

State the pipeline: `scrape → extract → verify → match → explain → UI`

---

## 5. Data Collection

**5.1 Sources and why they changed.** This is a genuine methodological finding,
not an apology. Report it:

| Source | Role | Outcome |
|---|---|---|
| Ministry guideline PDFs | first attempt | 12 docs, 253 sections — **rejected** |
| Wikipedia | discovery | 141 records, no eligibility content |
| myscheme.gov.in | final corpus | **37 schemes, 37/37 with an Eligibility section** |

The PDFs describe how programmes are *administered* — premium remittance,
insurer empanelment — not who qualifies. Three independent extractors each
found ~2 rules per 40 sections on that corpus. **The bottleneck was the source
documents, not the models.**

**5.2 Access method and ethics.** myscheme.gov.in is a client-rendered app
whose API is key-gated. Pages are rendered in a headless browser as an ordinary
visitor would, rate-limited, and cached so each is fetched once. `robots.txt`
permits crawling. The key-gated API was deliberately **not** used, as that
would mean working around an access control.

**5.3 Corpus statistics.** 37 schemes · 82 annotated sections (37 Eligibility,
9 Exclusions, 36 Benefits as labelled negatives) · **116 gold rules**.
Only ~6 schemes are strictly agricultural — state this, see §11.

---

## 6. Schema Design

**33 fields, 10 operators.** Data comes from `src/schema/fields.py`.

Design decisions worth a paragraph each:

- **`negated` is a flag, not an operator.** "must not be a government employee"
  is `eq false, negated=true`, never `neq`. Kept separate so negation
  performance can be measured as its own phenomenon.
- **Units recorded verbatim.** Acres stay acres; conversion happens at match
  time. Silent conversion by an annotator is unrecoverable.
- **`mandatory` vs preferential.** Preference affects ranking, never
  eligibility.
- **Vocabulary grew from the data.** Seven fields (`is_bpl`,
  `employment_status`, `is_loan_defaulter`, `education_level`, `years_farming`,
  `residence_type`, `one_per_family`) were added after annotation revealed
  criteria with nowhere to go.

---

## 7. Extraction Methods (M1)

Three extractors, all scored on identical gold:

1. **Regex baseline** — hand-written patterns for recurring criteria.
   Deliberately a strong baseline: a weak one makes any model look good.
2. **LLM extractor** — few-shot structured extraction against a local
   `qwen2.5:3b` via Ollama. Temperature 0, responses cached by prompt hash, so
   results are reproducible.
3. **Hybrid** — union of the two, regex winning ties.

Note the local model choice: fully offline, no API cost, no data leaves the
machine. A hosted model (`gemini-3.6-flash`) was evaluated and abandoned after
free-tier quota exhaustion — worth one honest sentence.

---

## 8. Evaluation Methodology

**8.1 Match criterion.** Exact `(field, op, normalised value)`. No partial
credit — a rule with the right field but wrong operator would admit ineligible
farmers.

**8.2 Why `negated` is excluded from the match key.** It records how a
criterion was *phrased*, not what it *is*. Including it double-penalised a
model that extracted the right condition with the wrong metadata. Reported as
its own metric instead.

**8.3 Held-out split.** 62 dev / 20 test, stratified by section type, keyed on
a hash of the section id — deterministic, no stored seed. Prompts were tuned on
dev; **test was read once, after tuning stopped**.

**8.4 Metrics.** Micro P/R/F1 · per-field F1 · negation-only F1 ·
negation-flag agreement · no-rules accuracy (hallucination rate on text
containing no criteria).

---

## 9. Results

**Source: `reports/ablation.md`.** Reproduce both tables.

**9.1 Main result (held-out test, n=20 rules):**

| Extractor | dev F1 | **test F1** |
|---|---|---|
| regex baseline | 0.493 | 0.444 |
| local 3B, 5-shot | 0.557 | 0.615 |
| **hybrid** | 0.663 | **0.683** |

Ranking is preserved dev→test and the hybrid does not degrade, so the gain
reflects real improvement rather than memorisation.

**9.2 Complementary failure.** The central finding — neither extractor
dominates:

| field | regex F1 | llm F1 |
|---|---|---|
| state | **0.98** | 0.73 |
| land_ownership | **1.00** | 0.00 |
| is_bpl | 0.00 | **1.00** |
| is_loan_defaulter | 0.00 | **0.91** |
| has_bank_account | 0.00 | **1.00** |

Regex is silent where it has no pattern; the model generalises but is noisier.

**9.3 Negation.** The baseline scores **exactly 0.000** on 13 negated
conditions *despite having negation patterns*. Real exclusions are phrased in
ways it cannot anticipate. The model reaches **0.818 with precision 1.000**.
This is the single strongest argument for a learned component.

**9.4 Prompt ablation.** One added few-shot example moved every metric:
F1 0.409 → 0.568, `state` F1 0.21 → 0.73. Precision was predicted to fall and
**rose** — few-shot examples teach which fields exist, not just output format.

**9.5 Source verification.** From `reports/source_verification.md`: 12 schemes
re-fetched live, **0/12 pages drifted**, **68/68 rules had textual support**,
no fabricated rule found. Report the caveat about how the 100% was obtained.

---

## 10. Matching Engine

Three verdicts, not two: `ELIGIBLE` / `NEED_INFO` / `NOT_ELIGIBLE`.

The design argument: **a blank answer is never a rejection.** Farmers do not
fill twenty fields; treating unknown as failure would hide schemes they qualify
for — the exact problem the system exists to solve. Pinned by tests.

Also cover: schemes with no extractable criteria are flagged, not reported as
eligible (absence of evidence is not qualification), and the "next best
question" ranks unanswered fields by how many schemes each would resolve.

**19 tests** covering the verdict contract, unit conversion, derived fields,
and localisation coverage.

---

## 11. Interface and Localisation

Streamlit, English + Hindi. The design argument worth making:

> Explanations are *composed*, not machine-translated. `Rule.human()` builds
> them from a field, operator and value — all closed vocabularies. Translating
> the vocabulary and recomposing in Hindi word order is exact and instant;
> machine-translating the assembled English would degrade already-awkward text.

Hindi is SOV where English is SVO, so operators carry their own templates, and
possessives/verbs agree with each noun's grammatical gender (`आपकी आयु` but
`आपका राज्य`).

Screenshots: English results, Hindi results, "not eligible with reasons".

---

## 12. Limitations and Threats to Validity

**Be exhaustive here. Examiners trust reports that pre-empt their questions.**

1. **Single annotator.** 116 rules labelled in one pass by one annotator.
   Cohen's κ **not measured**. `eval/agreement.py` implements it and
   `data/gold/annotator_b.jsonl` is prepared; the measurement is outstanding.
2. **Small test set.** 20 gold rules. Wide confidence intervals; per-field
   test figures are not meaningful (negation F1 1.000 rests on support of 2).
3. **Corpus scale and skew.** 37 schemes, ~6 strictly agricultural.
   Categories were widened to work around shallow pagination.
4. **Source verification is not fully independent** — see §9.5.
5. **`education_level` scores 0.00** for every extractor.
6. **Deployment gap.** The Ollama extractor cannot run on Streamlit Cloud;
   extraction is a build-time step.

---

## 13. Conclusion and Future Work  `[WRITE]`

Future work, in defensible priority order:

1. Measure κ; grow the gold set to 300+ rules
2. Scale the corpus via state-filtered scraping
3. Semantic retrieval (M3) for natural-language queries
4. Learned ranking (M4) over eligible schemes
5. Voice input and IndicTrans2 for scheme names
6. Deadline alerts and document checklists

---

## 14. References  `[WRITE]`

Cite only what you have read. Include: myscheme.gov.in, Agriculture Census
(size classes), Ollama/Qwen2.5, Streamlit, and your Related Work sources.

---

## Appendix — a methodology note worth including

Three times in this project a bad-looking number was a **broken measurement**,
not a broken system:

1. Extraction appeared to fail on ministry PDFs → the **corpus** contained no
   farmer eligibility
2. Eight schemes appeared to lack Eligibility sections → a **render race**
   captured pages before the section loaded
3. 14 rules appeared unsupported → the **checker's vocabulary** was too literal

Each looked like a quality problem and was an instrumentation problem. Stating
this shows methodological maturity and it is genuinely the most transferable
lesson in the project.

---

## Figures to produce

| Figure | Source |
|---|---|
| Architecture diagram | `README.md` |
| Held-out results table | `reports/ablation.md` |
| Per-field complementarity | `reports/ablation.md` |
| Prompt ablation before/after | `reports/ablation.md` |
| UI screenshots (EN + HI) | run the app |
| Verdict distribution for a sample profile | `python -m src.match.demo` |
