# Annotation brief — second annotator

**Time needed:** ~25 minutes for 20 sections, plus 5 minutes of setup.

## What you are doing and why

Our system reads government scheme pages and extracts eligibility criteria into
structured rules. To prove those extractions are accurate, we compare them
against a hand-labelled "gold" set.

But a gold set labelled by one person is just one person's opinion. To show it
is a *measurement*, two people must label the **same sections independently**
and we compute an agreement score (Cohen's kappa). That is your job.

**Do not look at `data/gold/candidates.jsonl`.** It contains the first
annotator's answers. If you see them, you will unconsciously agree with them,
the kappa score will be inflated, and the whole exercise becomes worthless.
Work only from the raw text in your file.

Disagreeing is fine and useful. Where we disagree tells us our guidelines are
ambiguous, which is something we need to know.

## Setup on your laptop (5 minutes)

**1. Install Python** — get 3.12 from python.org if you do not have it.
On Windows, tick **"Add Python to PATH"** during install or nothing below
works. Verify with `python --version`.

**2. Get the project.** Either clone it:

```
git clone https://github.com/shivenkhandelwal27-afk/kisan-mitra.git
cd kisan-mitra
```

…or download the ZIP from the GitHub page (green **Code** button →
*Download ZIP*) and unzip it. Git is not required.

**3. Install the two dependencies:**

```
pip install -r requirements.txt
```

That is `streamlit` and `pydantic` only — nothing heavy, no models to
download, works offline afterwards.

**4. Start the tool:**

```
streamlit run app/annotate.py
```

Your browser opens at `localhost:8501`. If it does not, copy the URL the
terminal prints.

**Troubleshooting**

- `'python' is not recognized` → Python is not on PATH. Reinstall with the
  PATH box ticked, or use `py` instead of `python`.
- `'streamlit' is not recognized` → use `python -m streamlit run app/annotate.py`
- `No module named src` → you are in the wrong folder. `cd` into `kisan-mitra`
  (the one containing `app/` and `src/`) first.

## Files you need

1. `data/gold/annotator_b.jsonl` — your worksheet, 20 sections
2. `docs/ANNOTATION_GUIDELINES.md` — the reference. You do **not** need to read
   it end to end; the tool shows the relevant rule for each section as you go.

## How to work

Use the tool (`streamlit run app/annotate.py`) rather than editing the file
by hand — it validates every rule as you add it, so you cannot produce a
broken label, and it saves after every click.

If you would rather edit the raw file: each line is one section; read the
`text` field and fill in the `rules` list.

Each line starts like this:

```json
{"id": "fe1767f4ca9d77f7", "section": "Eligibility",
 "doc": "Skilled Youth Startup Scheme",
 "text": "Applicant must be unemployed and have completed at least Class V...
          Applicant must be between 18 to 45 years of age...",
 "rules": [], "no_rules": false, "verified": false, "annotator": "B"}
```

You change `rules`, `no_rules` and `verified`. Leave `id`, `text`, `section`
and `doc` untouched.

Finished, it looks like this:

```json
"rules": [
  {"field": "employment_status", "op": "eq", "value": "unemployed"},
  {"field": "education_level", "op": "eq", "value": "class_5"},
  {"field": "age", "op": "gte", "value": 18, "unit": "years"},
  {"field": "age", "op": "lte", "value": 45, "unit": "years"}
],
"verified": true
```

If a section states **no** condition about a person (many `Benefits` sections
just describe what you receive), leave `rules` empty and set
`"no_rules": true, "verified": true`. **These matter** — they prove the system
does not invent criteria out of thin air. Do not skip them.

## The rules of thumb

Full detail is in `ANNOTATION_GUIDELINES.md`. The five that catch people out:

1. **One condition per rule.** "aged 18 to 45" is TWO rules (`gte 18`,
   `lte 45`), not one.
2. **Negation is a flag.** "must not be a government employee" is
   `{"field": "is_govt_employee", "op": "eq", "value": false, "negated": true}`
   — not `"op": "neq"`.
3. **Preference is not a requirement.** "preference given to women" means
   `"mandatory": false`. It affects ranking, never eligibility.
4. **Never convert units.** If it says acres, write `"unit": "acre"`. The code
   converts later. Converting yourself breaks the comparison.
5. **Only use fields that exist.** The valid field names are listed in
   `src/schema/fields.py`. If a criterion has no matching field, do **not**
   invent one — leave it out and set `"needs_field": true` on that line, then
   tell us.

## Common fields

`state` `age` `gender` `social_category` `annual_income` `land_ha`
`farmer_class` `land_ownership` `is_bpl` `has_bank_account` `has_kcc`
`is_govt_employee` `is_pensioner` `is_loan_defaulter` `education_level`
`employment_status` `residence_type` `one_per_family` `is_differently_abled`

Operators: `eq` `neq` `lt` `lte` `gt` `gte` `in` `not_in` `between` `exists`

## When you finish

Send the file back. We run:

```bash
python -m eval.agreement data/gold/candidates.jsonl data/gold/annotator_b.jsonl
```

Above 0.6 means our gold set holds up. Below 0.4 means the guidelines are
ambiguous and we rewrite them, then both relabel. Either outcome is a result.

## If you get stuck

Ask about *process* ("should a group-size rule count?") but never ask what the
other annotator wrote for a specific section. Note your uncertainty in a
`"note"` field on that line and move on — flagged disagreements are more
valuable than guesses.
