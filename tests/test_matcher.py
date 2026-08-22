"""Matcher behaviour tests.

These encode decisions that are easy to regress silently -- particularly the
unknown-vs-failed distinction, which decides whether a farmer sees a scheme at
all.
"""
from __future__ import annotations

import pytest

from src.match.engine import Verdict, check_rule, match_scheme
from src.schema.models import Operator, Rule, Scheme, SchemeCategory


def mk_scheme(rules, **kw):
    return Scheme(id="t", name={"en": "Test"}, category=SchemeCategory.SUBSIDY_INPUT,
                  level="central", source_url="http://x", eligibility=rules, **kw)


# --- the three-verdict contract ------------------------------------------
def test_all_satisfied_is_eligible():
    s = mk_scheme([Rule(field="age", op=Operator.GTE, value=18),
                   Rule(field="state", op=Operator.EQ, value="ASSAM")])
    r = match_scheme(s, {"age": 30, "state": "ASSAM"})
    assert r.verdict is Verdict.ELIGIBLE
    assert len(r.passed) == 2


def test_missing_field_is_need_info_not_rejection():
    """A blank answer must never be read as disqualifying."""
    s = mk_scheme([Rule(field="age", op=Operator.GTE, value=18),
                   Rule(field="has_kcc", op=Operator.EQ, value=True)])
    r = match_scheme(s, {"age": 30})
    assert r.verdict is Verdict.NEED_INFO
    assert r.missing_fields == ["has_kcc"]


def test_contradiction_is_not_eligible_with_reason():
    s = mk_scheme([Rule(field="age", op=Operator.LTE, value=40)])
    r = match_scheme(s, {"age": 55})
    assert r.verdict is Verdict.NOT_ELIGIBLE
    assert "55" in r.failed[0].explain()


def test_failure_outranks_unknown():
    """One hard failure decides the verdict even if other fields are blank."""
    s = mk_scheme([Rule(field="state", op=Operator.EQ, value="PUNJAB"),
                   Rule(field="has_kcc", op=Operator.EQ, value=True)])
    r = match_scheme(s, {"state": "KERALA"})
    assert r.verdict is Verdict.NOT_ELIGIBLE


# --- preferential criteria ------------------------------------------------
def test_preference_does_not_gate_eligibility():
    s = mk_scheme([Rule(field="age", op=Operator.GTE, value=18),
                   Rule(field="gender", op=Operator.EQ, value="female",
                        mandatory=False)])
    r = match_scheme(s, {"age": 30, "gender": "male"})
    assert r.verdict is Verdict.ELIGIBLE          # not disqualified
    assert r.preferences_met == []

    r2 = match_scheme(s, {"age": 30, "gender": "female"})
    assert r2.verdict is Verdict.ELIGIBLE
    assert len(r2.preferences_met) == 1
    assert r2.score < r.score                      # ranks higher


# --- unit and derivation handling ----------------------------------------
def test_acre_rule_compares_against_hectare_profile():
    """Profiles are in hectares; rules keep source units verbatim."""
    s = mk_scheme([Rule(field="land_ha", op=Operator.LTE, value=5, unit="acre")])
    assert match_scheme(s, {"land_ha": 1.0}).verdict is Verdict.ELIGIBLE   # 5ac=2.02ha
    assert match_scheme(s, {"land_ha": 3.0}).verdict is Verdict.NOT_ELIGIBLE


def test_farmer_class_derived_from_land():
    s = mk_scheme([Rule(field="farmer_class", op=Operator.IN,
                        value=["small", "marginal"])])
    assert match_scheme(s, {"land_ha": 0.8}).verdict is Verdict.ELIGIBLE
    assert match_scheme(s, {"land_ha": 6.0}).verdict is Verdict.NOT_ELIGIBLE


def test_list_field_matches_on_intersection():
    s = mk_scheme([Rule(field="livestock", op=Operator.IN,
                        value=["cattle", "buffalo"])])
    assert match_scheme(s, {"livestock": ["goat", "cattle"]}).verdict is Verdict.ELIGIBLE
    assert match_scheme(s, {"livestock": ["poultry"]}).verdict is Verdict.NOT_ELIGIBLE


def test_type_mismatch_is_unknown_not_failure():
    """A malformed profile value must not deny a benefit outright."""
    c = check_rule(Rule(field="age", op=Operator.GTE, value=18), {"age": "thirty"})
    assert c.result is None


# --- ranking ---------------------------------------------------------------
def test_eligible_ranks_above_need_info_and_rejected():
    from src.match.engine import match_all
    a = mk_scheme([Rule(field="age", op=Operator.GTE, value=18)])
    b = mk_scheme([Rule(field="has_kcc", op=Operator.EQ, value=True)])
    c = mk_scheme([Rule(field="age", op=Operator.LTE, value=10)])
    order = [r.verdict for r in match_all([c, b, a], {"age": 30})]
    assert order == [Verdict.ELIGIBLE, Verdict.NEED_INFO, Verdict.NOT_ELIGIBLE]


def test_scheme_with_no_rules_is_not_reported_as_eligible():
    """Absence of criteria is an extraction gap, not a qualification.

    A rule-less scheme passes every check vacuously. Reporting that as
    ELIGIBLE tells a farmer they qualify when we simply could not read the
    scheme -- the most damaging kind of wrong answer this system can give.
    """
    s = mk_scheme([])
    r = match_scheme(s, {"age": 30, "state": "ASSAM"})
    assert r.verdict is Verdict.NEED_INFO
    assert r.no_criteria is True


def test_preference_only_scheme_also_flagged():
    """Preferences never gate, so a scheme with only preferences has no gates."""
    s = mk_scheme([Rule(field="gender", op=Operator.EQ, value="female",
                        mandatory=False)])
    assert match_scheme(s, {"gender": "female"}).no_criteria is True
