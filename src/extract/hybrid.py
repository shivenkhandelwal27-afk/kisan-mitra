"""Hybrid extractor: union of the regex baseline and the LLM.

Motivated by measurement, not intuition. Scored on the same 82-section gold
set, the two extractors fail in opposite directions:

    field              regex F1   llm F1
    state                  0.98     0.21
    land_ownership         1.00     0.00
    age                    0.53     0.37
    is_loan_defaulter      0.00     0.91
    is_bpl                 0.00     0.73
    has_bank_account       0.00     1.00
    gender                 0.00     0.56
    negation (overall)     0.00     0.70

Regex is precise on surface patterns it was written for (state names, tenure
words) and silent everywhere else. The model generalises to phrasings nobody
anticipated -- especially negation, where regex scores a flat zero -- but is
noisy and systematically forgets `state`.

Taking the union should lift recall above either. It will also inherit the
model's false positives, so precision is expected to fall: the honest claim is
better F1, not better precision.
"""
from __future__ import annotations

from ..schema.models import Rule
from . import baseline


def extract(text: str) -> list[Rule]:
    rules: list[Rule] = list(baseline.extract(text))

    try:
        from . import llm
        model_rules = llm.extract(text)
    except Exception:
        # A hybrid that dies when the model is unreachable is worse than one
        # that degrades to its regex half. The caller still gets results.
        model_rules = []

    # Regex wins ties. Where both propose the same (field, op, value) the
    # regex version is kept, because its precision on those fields is higher
    # and its `unit` handling is verbatim by construction.
    seen = {(r.field, r.op, str(r.value)) for r in rules}
    for r in model_rules:
        k = (r.field, r.op, str(r.value))
        if k not in seen:
            seen.add(k)
            rules.append(r)
    return rules
