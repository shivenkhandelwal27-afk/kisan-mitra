# Kisan Mitra — Eligibility Discovery for Government Farmer Schemes

A **neuro-symbolic** system that matches a farmer's profile against government
schemes, subsidies, loans and insurance programmes.

Neural components *understand* (extract rules from documents, interpret
natural-language queries, rank results). A symbolic engine *decides*. The
eligibility decision is deterministic and auditable by design — an LLM that
hallucinates a criterion would be indefensible in a system people rely on for
welfare access, and unmeasurable in an evaluation.

## Architecture

```
scheme PDFs ──▶ [M1 extraction] ──▶ structured rules ──┐
                                                        ▼
farmer input ──▶ [M2 ASR + MT] ──▶ profile + query ──▶ [symbolic matcher] ──▶ eligible set
                             └───▶ [M3 embeddings] ──▶ candidates ─┤
                                                                    ▼
                                                        [M4 learned ranker] ──▶ ranked results
```

## Status

| Phase | Component | State |
|---|---|---|
| 1 | Corpus + schema | **done** |
| 2 | M1 extraction + gold set | in progress |
| 3 | Symbolic matcher + API | — |
| 4 | Retrieval + ranking + ablations | — |
| 5 | Multilingual + demo | — |

## Setup

```bash
pip install -r requirements.txt
```

## Running Phase 1

```bash
python -m src.scrape.run
```

Builds `data/raw/` from two sources with complementary roles:

- **Wikipedia API** — *discovery*. Enumerates schemes, descriptions, state
  mapping. Spot-checking confirmed major articles (PM-KISAN included) carry no
  eligibility criteria, so it is deliberately **not** used for rules.
- **Official guideline PDFs** — *authority*. Operational guidelines from
  agriwelfare.gov.in and scheme portals. These state eligibility in full prose
  and are the M1 training material.

Then build the annotation queue:

```bash
python -m src.extract.candidates
```

Writes `data/gold/candidates.jsonl`, ordered by eligibility-cue density so the
most informative paragraphs are labelled first.

## Corpus sources

| Source | Role | Result |
|---|---|---|
| **myscheme.gov.in** | farmer eligibility | 37 schemes, **37/37 with an Eligibility section**, 11 with Exclusions, 82 annotatable sections |
| Ministry guideline PDFs | programme administration | 12 docs, 253 heuristic sections |
| Wikipedia | scheme discovery | 141 records |

### Why the corpus changed

The project was first built on ministry operational-guideline PDFs (MIDH, PMFBY,
ATMA). Those describe how programmes are *administered* -- how states remit
premium, how insurers are empanelled -- not which farmer qualifies. Three
independent extractors (regex, a local qwen2.5:3b, and gemini-3.6-flash) each
returned roughly 2 rules per 40 sections on that corpus.

Rule *counts* did not settle the question: the regex baseline appears to yield
more on PDFs (25 non-state rules vs 18), but inspection shows those are largely
false positives -- it fires on any mention of "KCC", which PMFBY guidelines use
constantly in administrative contexts. Both extractors were behaving correctly;
only the LLM was honest about finding nothing.

The decisive argument is structural, not numerical. myscheme sections are
eligibility statements **by construction** -- the government labels them
"Eligibility" -- whereas every PDF section was a guess made by a heuristic.
That is why myscheme sections enter the annotation queue at priority 1000,
ahead of every heuristically-scored PDF paragraph.

## Phase 1 outcome

| Metric | Value |
|---|---|
| Wikipedia scheme records | 141 |
| Official guideline PDFs parsed | 12 |
| Document sections after chunking | 1,091 |
| Eligibility-candidate sections | 253 (target: 250) |
| Median section length | 522 chars |
| Top-250 containing negation | 64% |

Candidate ranking is heuristic and imperfect by design — see the limitation
note in `docs/ANNOTATION_GUIDELINES.md`.

## Key files

| Path | Role |
|---|---|
| `src/schema/fields.py` | Controlled field vocabulary — **the contract** |
| `src/schema/models.py` | `Rule` / `Scheme` models with validation |
| `src/config.py` | Target states, rate limits, contact UA |
| `docs/ANNOTATION_GUIDELINES.md` | Labelling rules — lock before annotating |

## Data provenance

All sources are public. `robots.txt` was checked for every host and permits
crawling. Requests are disk-cached (`data/raw/_cache/`) so each document is
fetched exactly once, and rate-limited per host. myscheme.gov.in was evaluated
and **rejected** as a source: its scheme pages are client-rendered and its API
requires a key, so bulk collection would have meant working around an access
control.
