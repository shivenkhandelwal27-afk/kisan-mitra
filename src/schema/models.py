"""Core data models: eligibility rules and schemes.

An eligibility Rule carries the text span it was extracted from. That span is
what turns this dataset into supervised training data for M1 -- without it we
would only have a config file, not a corpus with labels grounded in the source.
"""

from __future__ import annotations

from datetime import date
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from .fields import FIELDS, DType


class Operator(str, Enum):
    EQ = "eq"
    NEQ = "neq"
    LT = "lt"
    LTE = "lte"
    GT = "gt"
    GTE = "gte"
    IN = "in"
    NOT_IN = "not_in"
    BETWEEN = "between"
    EXISTS = "exists"


class SchemeCategory(str, Enum):
    INCOME_SUPPORT = "income_support"
    CREDIT_LOAN = "credit_loan"
    INSURANCE = "insurance"
    SUBSIDY_INPUT = "subsidy_input"
    SUBSIDY_EQUIPMENT = "subsidy_equipment"
    IRRIGATION = "irrigation"
    PENSION_WELFARE = "pension_welfare"
    MARKET_ACCESS = "market_access"
    TRAINING = "training"
    INFRASTRUCTURE = "infrastructure"
    ALLIED_ACTIVITY = "allied_activity"   # dairy, poultry, fisheries, beekeeping


class SourceSpan(BaseModel):
    """Character offsets into Scheme.raw_eligibility_text."""
    text: str
    start: int = -1
    end: int = -1


class Rule(BaseModel):
    """One atomic eligibility condition."""
    field: str
    op: Operator
    value: Any = None
    unit: str | None = None
    # True when the source phrases the condition negatively ("must not be a
    # government employee"). Kept separate from the operator because negation
    # is the highest-error-rate phenomenon in M1 and we want to measure it.
    negated: bool = False
    # Mandatory conditions gate eligibility; preferential ones only affect
    # priority (e.g. "preference to women farmers").
    mandatory: bool = True
    source: SourceSpan | None = None
    note: str | None = None

    @field_validator("field")
    @classmethod
    def _known_field(cls, v: str) -> str:
        if v not in FIELDS:
            raise ValueError(
                f"unknown field {v!r}; add it to schema.fields.FIELDS first"
            )
        return v

    @model_validator(mode="after")
    def _value_matches_field(self) -> "Rule":
        if self.op is Operator.EXISTS:
            return self
        spec = FIELDS[self.field]
        if self.op is Operator.BETWEEN:
            if not (isinstance(self.value, list) and len(self.value) == 2):
                raise ValueError("BETWEEN needs a [lo, hi] value")
            return self
        if self.op in (Operator.IN, Operator.NOT_IN):
            if not isinstance(self.value, list):
                raise ValueError(f"{self.op} needs a list value")
            # Categorical members must be checked individually. This branch
            # used to return here after the isinstance check, so IN/NOT_IN
            # bypassed the allowed-values test entirely -- a model emitted
            # social_category IN ["general","SC","ST","BPL","Women","Landless"]
            # and it validated cleanly, putting three non-categories and a
            # wrong-case value into the gold set.
            if spec.dtype is DType.CATEGORICAL and spec.allowed:
                canon = {a.upper(): a for a in spec.allowed}
                fixed = []
                for v in self.value:
                    key = str(v).upper()
                    if key not in canon:
                        raise ValueError(
                            f"{v!r} is not a valid {self.field}; "
                            f"allowed: {', '.join(spec.allowed)}")
                    # Normalise case only -- same value, different spelling.
                    fixed.append(canon[key])
                object.__setattr__(self, "value", fixed)
            return self
        if not spec.validate_value(self.value):
            raise ValueError(
                f"value {self.value!r} invalid for field {self.field!r} "
                f"({spec.dtype.value}, allowed={spec.allowed})"
            )
        return self

    def human(self) -> str:
        """Plain-language rendering, used in the 'why' explanations."""
        # Words rather than symbols: these strings are read by farmers and are
        # machine-translated in the i18n layer, where "at most" survives and
        # a bare glyph does not.
        sym = {
            Operator.EQ: "is", Operator.NEQ: "is not",
            Operator.LT: "is under", Operator.LTE: "is at most",
            Operator.GT: "is over", Operator.GTE: "is at least",
            Operator.IN: "is one of", Operator.NOT_IN: "is not one of",
            Operator.BETWEEN: "is between", Operator.EXISTS: "must be provided",
        }[self.op]
        unit = f" {self.unit}" if self.unit else ""
        return f"{self.field.replace('_', ' ')} {sym} {self.value}{unit}".strip()


class Scheme(BaseModel):
    id: str
    name: dict[str, str]                    # {"en": ..., "hi": ...}
    category: SchemeCategory
    level: Literal["central", "state"]
    states: list[str] = Field(default_factory=lambda: ["ALL"])

    benefit_text: str = ""
    benefit_amount_inr: float | None = None

    eligibility: list[Rule] = Field(default_factory=list)
    documents: list[str] = Field(default_factory=list)

    apply_url: str | None = None
    source_url: str
    last_verified: date | None = None

    # Verbatim source text. This is the M1 model input; never edit it to make
    # extraction easier, or the evaluation stops measuring anything real.
    raw_eligibility_text: str = ""
    raw_benefit_text: str = ""

    # Set by the annotator once every rule in raw_eligibility_text is captured.
    gold_verified: bool = False

    def mandatory_rules(self) -> list[Rule]:
        return [r for r in self.eligibility if r.mandatory]


class SchemeCorpus(BaseModel):
    """Wrapper so the on-disk corpus is a single validated document."""
    schemes: list[Scheme]
    generated_at: date | None = None

    def by_id(self, scheme_id: str) -> Scheme | None:
        return next((s for s in self.schemes if s.id == scheme_id), None)
