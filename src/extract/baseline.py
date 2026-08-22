"""Rule-based baseline extractor:  the number M1 must beat.

Deliberately a strong baseline, not a strawman. A weak baseline makes any model
look good and tells your evaluator nothing. These patterns cover the criteria
that actually recur across Indian scheme guidelines, so beating this score means
the model genuinely handles phrasing that regex cannot.

Where it fails, and why that is the interesting part:
  - conditions split across clauses ("...provided that such farmer has not...")
  - negation scope ("not a government employee or income tax payee" -> 2 rules)
  - implicit subjects ("such beneficiaries shall also be covered")
  - anything phrased in a way the author did not anticipate
"""
from __future__ import annotations

import re

from ..schema.models import Rule, Operator, SourceSpan
from ..schema.fields import STATES

# ---------------------------------------------------------------- helpers ---
def _span(m: re.Match) -> SourceSpan:
    return SourceSpan(text=m.group(0).strip(), start=m.start(), end=m.end())


def _num(s: str) -> float:
    return float(s.replace(",", ""))


# ---------------------------------------------------------------- patterns ---
# Each entry: (compiled pattern, builder(match) -> list[Rule])

LAND_CAP = re.compile(
    r"(?:up ?to|not exceeding|maximum of|less than|below|within)\s*"
    r"(\d+(?:\.\d+)?)\s*(hectares?|ha\b|acres?)", re.I)

LAND_MIN = re.compile(
    r"(?:at least|minimum of|more than|above|not less than)\s*"
    r"(\d+(?:\.\d+)?)\s*(hectares?|ha\b|acres?)", re.I)

AGE_RANGE = re.compile(
    r"(?:aged?|age of|between)\s*(\d{1,2})\s*(?:to|-|and|—)\s*(\d{1,2})\s*years?", re.I)

AGE_MIN = re.compile(
    r"(?:aged?|age of|attained the age of)\s*(?:at least\s*)?(\d{1,2})\s*years?"
    r"(?!\s*(?:to|-|and))", re.I)

SMF = re.compile(r"small\s*(?:and|&|/)\s*marginal\s+farmers?", re.I)
SC_ST = re.compile(r"\bSC\s*/\s*ST\b|scheduled\s+castes?\s*(?:and|/|&)\s*scheduled\s+tribes?", re.I)
WOMEN = re.compile(r"\bwomen\s+farmers?|\bfemale\s+farmers?", re.I)

# Exclusion clauses. These are the negation cases the guidelines call out.
NOT_GOVT = re.compile(
    r"(?:not|shall not|should not|nor)\s+(?:be\s+)?(?:a\s+)?"
    r"(?:serving or retired\s+)?(?:government|govt\.?)\s+(?:servant|employee|official)", re.I)
NOT_TAX = re.compile(
    r"(?:income[- ]tax\s+pay(?:er|ee)s?|paid income tax)", re.I)
NOT_INSTITUTIONAL = re.compile(r"institutional\s+land\s*holders?", re.I)

TENANT = re.compile(r"\btenant\s+farmers?|share\s*croppers?", re.I)
LOANEE = re.compile(r"\bloanee\s+farmers?", re.I)
NON_LOANEE = re.compile(r"\bnon[- ]loanee\s+farmers?", re.I)
KCC = re.compile(r"Kisan\s+Credit\s+Card|\bKCC\b", re.I)

PENSION_CAP = re.compile(
    r"pension\s+of\s*(?:more than\s*)?₹?\s*([\d,]+)\s*(?:/-)?\s*(?:per month|/month|pm\b)", re.I)


def extract(text: str) -> list[Rule]:
    """Return every rule the pattern set can find in a paragraph."""
    out: list[Rule] = []

    for m in LAND_CAP.finditer(text):
        unit = "acre" if m.group(2).lower().startswith("acre") else "hectare"
        out.append(Rule(field="land_ha", op=Operator.LTE, value=_num(m.group(1)),
                        unit=unit, source=_span(m)))
    for m in LAND_MIN.finditer(text):
        unit = "acre" if m.group(2).lower().startswith("acre") else "hectare"
        out.append(Rule(field="land_ha", op=Operator.GTE, value=_num(m.group(1)),
                        unit=unit, source=_span(m)))

    for m in AGE_RANGE.finditer(text):
        out.append(Rule(field="age", op=Operator.GTE, value=int(m.group(1)),
                        unit="years", source=_span(m)))
        out.append(Rule(field="age", op=Operator.LTE, value=int(m.group(2)),
                        unit="years", source=_span(m)))
    if not AGE_RANGE.search(text):
        for m in AGE_MIN.finditer(text):
            out.append(Rule(field="age", op=Operator.GTE, value=int(m.group(1)),
                            unit="years", source=_span(m)))

    for m in SMF.finditer(text):
        out.append(Rule(field="farmer_class", op=Operator.IN,
                        value=["small", "marginal"], source=_span(m)))
    for m in SC_ST.finditer(text):
        out.append(Rule(field="social_category", op=Operator.IN,
                        value=["SC", "ST"], source=_span(m)))
    for m in WOMEN.finditer(text):
        # "preference to women farmers" is a ranking signal, not a gate.
        pref = bool(re.search(r"prefer|priority|encourag", text, re.I))
        out.append(Rule(field="gender", op=Operator.EQ, value="female",
                        mandatory=not pref, source=_span(m)))

    for m in NOT_GOVT.finditer(text):
        out.append(Rule(field="is_govt_employee", op=Operator.EQ, value=False,
                        negated=True, source=_span(m)))
    for m in NOT_TAX.finditer(text):
        out.append(Rule(field="is_income_tax_payer", op=Operator.EQ, value=False,
                        negated=True, source=_span(m)))
    for m in NOT_INSTITUTIONAL.finditer(text):
        out.append(Rule(field="is_institutional_landholder", op=Operator.EQ,
                        value=False, negated=True, source=_span(m)))
    for m in PENSION_CAP.finditer(text):
        out.append(Rule(field="pension_amount_monthly", op=Operator.LTE,
                        value=_num(m.group(1)), unit="INR", negated=True,
                        source=_span(m)))

    for m in TENANT.finditer(text):
        out.append(Rule(field="land_ownership", op=Operator.IN,
                        value=["tenant", "sharecropper"], source=_span(m)))
    for m in NON_LOANEE.finditer(text):
        out.append(Rule(field="has_kcc", op=Operator.EQ, value=False,
                        negated=True, source=_span(m)))
    if not NON_LOANEE.search(text):
        for m in LOANEE.finditer(text):
            out.append(Rule(field="has_kcc", op=Operator.EQ, value=True, source=_span(m)))
    if not LOANEE.search(text) and not NON_LOANEE.search(text):
        for m in KCC.finditer(text):
            out.append(Rule(field="has_kcc", op=Operator.EQ, value=True, source=_span(m)))

    for state in STATES:
        if state == "ALL":
            continue
        pretty = state.replace("_", " ").title()
        m = re.search(rf"\b{re.escape(pretty)}\b", text)
        if m:
            out.append(Rule(field="state", op=Operator.EQ, value=state, source=_span(m)))

    # De-duplicate identical triples produced by overlapping patterns.
    seen, uniq = set(), []
    for r in out:
        key = (r.field, r.op, str(r.value), r.negated)
        if key not in seen:
            seen.add(key); uniq.append(r)
    return uniq
