"""Localisation coverage.

The point of these tests is that a MISSING translation must fail loudly here
rather than silently showing English to a Hindi-speaking farmer.
"""
from src.i18n.hindi import FIELD_HI, OP_HI, check_text, rule_text
from src.match.engine import check_rule
from src.schema.fields import FIELDS
from src.schema.models import Operator, Rule


def test_every_schema_field_has_hindi():
    missing = sorted(set(FIELDS) - set(FIELD_HI))
    assert not missing, f"no Hindi for: {missing}"


def test_every_operator_has_hindi_template():
    assert sorted(OP_HI) == sorted(Operator)


def test_rule_renders_in_hindi_word_order():
    r = Rule(field="age", op=Operator.GTE, value=18, unit="years")
    assert rule_text(r, "hi") == "आयु कम से कम 18 वर्ष"
    assert rule_text(r, "en") == "age is at least 18 years"


def test_categorical_values_are_translated_not_passed_through():
    r = Rule(field="social_category", op=Operator.IN, value=["SC", "ST"])
    hi = rule_text(r, "hi")
    assert "अनुसूचित जाति" in hi and "SC" not in hi


def test_state_names_translated():
    r = Rule(field="state", op=Operator.EQ, value="ASSAM")
    assert "असम" in rule_text(r, "hi")


def test_check_explanations_localise():
    r = Rule(field="age", op=Operator.LTE, value=40, unit="years")
    c = check_rule(r, {"age": 55})
    hi = check_text(c, "hi")
    assert "55" in hi and "आयु" in hi
    assert "but this scheme needs" not in hi


def test_unknown_check_localises():
    c = check_rule(Rule(field="has_kcc", op=Operator.EQ, value=True), {})
    assert "किसान क्रेडिट कार्ड" in check_text(c, "hi")
