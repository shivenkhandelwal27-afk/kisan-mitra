"""Symbolic eligibility matcher — the deciding half of the system.

Deliberately contains no machine learning. Extraction is where language
understanding is needed and where errors are measured; the DECISION must be
deterministic, inspectable, and explainable, because a farmer denied a benefit
deserves a reason a human can audit, and "the model said so" is not one.

Three verdicts, not two:

    ELIGIBLE      every mandatory condition is satisfied
    NEED_INFO     nothing failed, but the profile is missing an answer
    NOT_ELIGIBLE  at least one mandatory condition is contradicted

NEED_INFO exists because a farmer will not fill in every field. Treating
unknown as failure would silently hide schemes they may well qualify for --
the exact problem this project exists to solve.
"""
from __future__ import annotations

from dataclasses import dataclass, field as dc_field
from enum import Enum
from typing import Any

from ..schema.fields import FIELDS, DType, derive_farmer_class, to_hectares
from ..schema.models import Operator, Rule, Scheme


class Verdict(str, Enum):
    ELIGIBLE = "eligible"
    NEED_INFO = "need_info"
    NOT_ELIGIBLE = "not_eligible"


@dataclass
class Check:
    """One rule evaluated against one profile."""
    rule: Rule
    result: bool | None          # None means the profile does not say
    actual: Any = None

    def explain(self) -> str:
        name = self.rule.field.replace("_", " ")
        if self.result is None:
            return f"we need to know your {name}"
        if self.result:
            return f"your {name} ({_fmt(self.actual)}) meets: {self.rule.human()}"
        return f"your {name} is {_fmt(self.actual)}, but this scheme needs {self.rule.human()}"


@dataclass
class MatchResult:
    scheme: Scheme
    verdict: Verdict
    passed: list[Check] = dc_field(default_factory=list)
    failed: list[Check] = dc_field(default_factory=list)
    unknown: list[Check] = dc_field(default_factory=list)
    preferences_met: list[Check] = dc_field(default_factory=list)
    # True when the scheme has no usable criteria at all (extraction gap).
    no_criteria: bool = False

    @property
    def missing_fields(self) -> list[str]:
        return sorted({c.rule.field for c in self.unknown})

    @property
    def score(self) -> tuple:
        """Ranking key. Eligible first; among those, most preferences met.

        Within NEED_INFO, schemes needing the fewest extra answers rank higher
        -- those are the ones a farmer can resolve with the least effort.
        """
        order = {Verdict.ELIGIBLE: 0, Verdict.NEED_INFO: 1, Verdict.NOT_ELIGIBLE: 2}
        # Schemes we could not read rank below ones we genuinely evaluated.
        return (order[self.verdict], int(self.no_criteria),
                -len(self.preferences_met),
                len(self.missing_fields),
                -len(self.passed))


def _fmt(v: Any) -> str:
    if v is None:
        return "not provided"
    if isinstance(v, bool):
        return "yes" if v else "no"
    if isinstance(v, list):
        return ", ".join(map(str, v)) or "none"
    return str(v)


def _profile_value(field: str, profile: dict) -> Any:
    """Read a field, deriving it where the schema says it is derivable."""
    if field in profile and profile[field] is not None:
        return profile[field]
    # farmer_class is defined as a function of land size, so a profile that
    # gives land_ha implicitly answers it.
    if field == "farmer_class":
        return derive_farmer_class(profile.get("land_ha"))
    return None


def _expected(rule: Rule) -> Any:
    """Rule value in comparison units (profile land is always hectares)."""
    if rule.field == "land_ha" and rule.unit:
        try:
            if isinstance(rule.value, list):
                return [to_hectares(float(v), rule.unit) for v in rule.value]
            return to_hectares(float(rule.value), rule.unit)
        except (ValueError, TypeError):
            return rule.value
    return rule.value


def check_rule(rule: Rule, profile: dict) -> Check:
    actual = _profile_value(rule.field, profile)
    expected = _expected(rule)

    if rule.op is Operator.EXISTS:
        return Check(rule, actual is not None, actual)
    if actual is None:
        return Check(rule, None, None)

    spec = FIELDS.get(rule.field)
    try:
        # List-valued fields (crops, livestock) match on intersection: a farmer
        # who owns cattle AND goats satisfies "livestock in [cattle, buffalo]".
        if spec and spec.dtype is DType.LIST and isinstance(actual, list):
            want = expected if isinstance(expected, list) else [expected]
            hit = bool({str(a).lower() for a in actual} &
                       {str(w).lower() for w in want})
            if rule.op is Operator.NOT_IN:
                return Check(rule, not hit, actual)
            return Check(rule, hit, actual)

        if rule.op is Operator.EQ:
            ok = actual == expected
        elif rule.op is Operator.NEQ:
            ok = actual != expected
        elif rule.op is Operator.LT:
            ok = actual < expected
        elif rule.op is Operator.LTE:
            ok = actual <= expected
        elif rule.op is Operator.GT:
            ok = actual > expected
        elif rule.op is Operator.GTE:
            ok = actual >= expected
        elif rule.op is Operator.IN:
            ok = actual in expected
        elif rule.op is Operator.NOT_IN:
            ok = actual not in expected
        elif rule.op is Operator.BETWEEN:
            ok = expected[0] <= actual <= expected[1]
        else:
            ok = None
    except TypeError:
        # Comparing incompatible types means the profile cannot answer this
        # rule, which is "unknown", not "failed". Reporting it as failure
        # would deny a farmer a scheme over a data-type mismatch.
        return Check(rule, None, actual)

    return Check(rule, ok, actual)


def match_scheme(scheme: Scheme, profile: dict) -> MatchResult:
    res = MatchResult(scheme=scheme, verdict=Verdict.ELIGIBLE)

    # A scheme with no extracted criteria passes every check vacuously, which
    # would tell a farmer "you qualify" when the truth is "we could not read
    # this scheme's rules". Absence of evidence is not eligibility, so it is
    # reported as NEED_INFO with an explicit reason instead.
    if not any(r.mandatory for r in scheme.eligibility):
        res.verdict = Verdict.NEED_INFO
        res.no_criteria = True
        return res

    for rule in scheme.eligibility:
        c = check_rule(rule, profile)
        if not rule.mandatory:
            # Preferential criteria never gate eligibility; they only raise
            # priority ("preference given to women farmers").
            if c.result:
                res.preferences_met.append(c)
            continue
        if c.result is None:
            res.unknown.append(c)
        elif c.result:
            res.passed.append(c)
        else:
            res.failed.append(c)

    if res.failed:
        res.verdict = Verdict.NOT_ELIGIBLE
    elif res.unknown:
        res.verdict = Verdict.NEED_INFO
    return res


def match_all(schemes: list[Scheme], profile: dict) -> list[MatchResult]:
    return sorted((match_scheme(s, profile) for s in schemes),
                  key=lambda r: r.score)


def load_schemes(path=None) -> list[Scheme]:
    import json
    from ..config import PROCESSED
    path = path or (PROCESSED / "schemes.json")
    data = json.loads(path.read_text(encoding="utf-8"))
    return [Scheme(**s) for s in data["schemes"]]
