"""Controlled vocabulary for farmer profile fields.

This module is the contract between every other part of the system. The M1
extraction model may only emit `field` values that appear in FIELDS, and the
symbolic matcher may only read profile keys that appear here. Locking this
down before annotation begins is what makes inter-annotator agreement
measurable at all.

Adding a field is cheap. Renaming one after labelling has started is not.
"""

from __future__ import annotations

from dataclasses import dataclass, field as dc_field
from enum import Enum
from typing import Any


class DType(str, Enum):
    NUMBER = "number"
    BOOL = "bool"
    CATEGORICAL = "categorical"
    LIST = "list"
    STRING = "string"


@dataclass(frozen=True)
class FieldSpec:
    name: str
    dtype: DType
    description: str
    unit: str | None = None
    allowed: tuple[str, ...] | None = None
    # Hints for the annotators + the extraction prompt.
    aliases: tuple[str, ...] = dc_field(default_factory=tuple)

    def validate_value(self, value: Any) -> bool:
        if self.dtype is DType.NUMBER:
            return isinstance(value, (int, float)) or (
                isinstance(value, list) and len(value) == 2  # for BETWEEN
            )
        if self.dtype is DType.BOOL:
            return isinstance(value, bool)
        if self.dtype is DType.CATEGORICAL:
            vals = value if isinstance(value, list) else [value]
            return self.allowed is not None and all(v in self.allowed for v in vals)
        if self.dtype is DType.LIST:
            return isinstance(value, list)
        return isinstance(value, str)


SOCIAL_CATEGORIES = ("SC", "ST", "OBC", "GENERAL", "MINORITY")
LAND_OWNERSHIP = ("owner", "tenant", "sharecropper", "landless", "joint")
IRRIGATION = ("rainfed", "canal", "borewell", "tank", "drip", "sprinkler", "none")
GENDERS = ("male", "female", "other")
# Derived from land_ha per the Agriculture Census size classes.
FARMER_CLASSES = ("marginal", "small", "semi_medium", "medium", "large")
EMPLOYMENT = ("unemployed", "salaried", "self_employed", "govt_employee",
              "pensioner", "student")
EDUCATION = ("none", "primary", "class_5", "class_8", "class_10", "class_12",
             "graduate", "technical")
RESIDENCE = ("rural", "urban", "both")

STATES = (
    "ANDHRA_PRADESH", "ARUNACHAL_PRADESH", "ASSAM", "BIHAR", "CHHATTISGARH",
    "GOA", "GUJARAT", "HARYANA", "HIMACHAL_PRADESH", "JHARKHAND", "KARNATAKA",
    "KERALA", "MADHYA_PRADESH", "MAHARASHTRA", "MANIPUR", "MEGHALAYA",
    "MIZORAM", "NAGALAND", "ODISHA", "PUNJAB", "RAJASTHAN", "SIKKIM",
    "TAMIL_NADU", "TELANGANA", "TRIPURA", "UTTAR_PRADESH", "UTTARAKHAND",
    "WEST_BENGAL", "ALL",
)

FIELDS: dict[str, FieldSpec] = {
    f.name: f
    for f in [
        # --- identity / demographics -------------------------------------
        FieldSpec("state", DType.CATEGORICAL, "State of residence/landholding",
                  allowed=STATES),
        FieldSpec("district", DType.STRING, "District name"),
        FieldSpec("age", DType.NUMBER, "Age of the applicant", unit="years",
                  aliases=("aged", "years of age", "आयु")),
        FieldSpec("gender", DType.CATEGORICAL, "Gender", allowed=GENDERS),
        FieldSpec("social_category", DType.CATEGORICAL,
                  "Reservation category", allowed=SOCIAL_CATEGORIES,
                  aliases=("scheduled caste", "scheduled tribe", "general category")),
        FieldSpec("is_differently_abled", DType.BOOL, "Has a disability certificate"),

        # --- land ---------------------------------------------------------
        FieldSpec("land_ha", DType.NUMBER, "Total operational landholding",
                  unit="hectare",
                  aliases=("acre", "hectare", "landholding", "cultivable land")),
        FieldSpec("land_ownership", DType.CATEGORICAL,
                  "Tenure type over the cultivated land", allowed=LAND_OWNERSHIP),
        FieldSpec("farmer_class", DType.CATEGORICAL,
                  "Census size class, DERIVED from land_ha", allowed=FARMER_CLASSES,
                  aliases=("small and marginal farmer", "SMF")),
        FieldSpec("has_land_records", DType.BOOL,
                  "Holds recorded title (khatauni / pattadar passbook / 7-12)"),

        # --- economic -----------------------------------------------------
        FieldSpec("annual_income", DType.NUMBER, "Annual household income",
                  unit="INR"),
        FieldSpec("is_income_tax_payer", DType.BOOL,
                  "Paid income tax in the last assessment year"),
        FieldSpec("is_govt_employee", DType.BOOL,
                  "Serving or retired government employee"),
        FieldSpec("is_pensioner", DType.BOOL, "Draws a pension"),
        FieldSpec("pension_amount_monthly", DType.NUMBER,
                  "Monthly pension drawn", unit="INR"),
        FieldSpec("is_institutional_landholder", DType.BOOL,
                  "Land held by an institution rather than an individual"),

        # --- agricultural practice ----------------------------------------
        FieldSpec("crops", DType.LIST, "Crops currently grown"),
        FieldSpec("livestock", DType.LIST, "Livestock owned"),
        FieldSpec("irrigation_source", DType.CATEGORICAL,
                  "Primary irrigation source", allowed=IRRIGATION),
        FieldSpec("is_organic_farmer", DType.BOOL, "Practises certified organic farming"),

        # --- financial inclusion -------------------------------------------
        FieldSpec("has_kcc", DType.BOOL, "Holds a Kisan Credit Card"),
        FieldSpec("has_aadhaar_linked_bank", DType.BOOL,
                  "Bank account seeded with Aadhaar"),
        FieldSpec("has_bank_account", DType.BOOL, "Holds any bank account"),

        # --- socio-economic status -------------------------------------------
        # Added after annotating the myscheme corpus: these criteria recur
        # across welfare, credit and pension schemes and had nowhere to go,
        # which would have forced the annotator to drop real conditions.
        FieldSpec("is_bpl", DType.BOOL, "Holds a Below Poverty Line card",
                  aliases=("BPL", "below poverty line")),
        FieldSpec("employment_status", DType.CATEGORICAL,
                  "Work status of the applicant", allowed=EMPLOYMENT,
                  aliases=("unemployed", "salaried", "self-employed")),
        FieldSpec("is_loan_defaulter", DType.BOOL,
                  "In default to any bank or financial institution",
                  aliases=("NPA", "defaulter", "in default")),
        FieldSpec("education_level", DType.CATEGORICAL,
                  "Highest level of schooling completed", allowed=EDUCATION),
        FieldSpec("years_farming", DType.NUMBER,
                  "Years of continuous cultivation experience", unit="years"),
        FieldSpec("residence_type", DType.CATEGORICAL,
                  "Rural or urban residence", allowed=RESIDENCE),
        FieldSpec("one_per_family", DType.BOOL,
                  "Only one member of a family may benefit"),

        # --- affiliation ----------------------------------------------------
        FieldSpec("fpo_member", DType.BOOL, "Member of a Farmer Producer Organisation"),
        FieldSpec("shg_member", DType.BOOL, "Member of a Self Help Group"),
        FieldSpec("existing_schemes", DType.LIST, "Scheme ids already enrolled in"),
    ]
}

# Agriculture Census operational-holding size classes, in hectares.
FARMER_CLASS_BOUNDS: tuple[tuple[str, float, float], ...] = (
    ("marginal", 0.0, 1.0),
    ("small", 1.0, 2.0),
    ("semi_medium", 2.0, 4.0),
    ("medium", 4.0, 10.0),
    ("large", 10.0, float("inf")),
)


def derive_farmer_class(land_ha: float | None) -> str | None:
    """Map a landholding size onto its Census class."""
    if land_ha is None:
        return None
    for name, lo, hi in FARMER_CLASS_BOUNDS:
        if lo <= land_ha < hi:
            return name
    return None


ACRE_TO_HECTARE = 0.404686


def to_hectares(value: float, unit: str) -> float:
    """Normalise a land figure to hectares.

    Scheme documents mix acres and hectares freely, sometimes within one
    sentence. Unit errors are the single largest source of false matches, so
    every land value passes through here.
    """
    u = unit.strip().lower()
    if u in {"ha", "hectare", "hectares", "हेक्टेयर"}:
        return value
    if u in {"acre", "acres", "एकड़"}:
        return value * ACRE_TO_HECTARE
    raise ValueError(f"unknown land unit: {unit!r}")
