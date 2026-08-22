"""Hindi localisation.

WHY THIS IS NOT MACHINE TRANSLATION
Eligibility explanations are not free text -- they are composed by
Rule.human() from three parts: a field, an operator, and a value. Every one of
those parts comes from a CLOSED vocabulary defined in schema/fields.py.

Machine-translating the assembled English ("land ha is at most 2 hectare")
would feed a translator text that is already awkward and produce something
worse. Translating the vocabulary and recomposing in Hindi word order is
deterministic, instant, offline, free, and correct -- and it cannot drift,
because a field with no Hindi entry fails loudly in tests rather than silently
emitting English to a farmer.

Hindi is SOV where English is SVO, so operators carry their own templates
rather than being substituted word-for-word:

    en:  age is at least 18 years
    hi:  आयु कम से कम 18 वर्ष

Scheme names and benefit descriptions are free-form text scraped from the
portal and are NOT covered here. They stay in English, flagged as such in the
UI. Translating them needs a real MT model (IndicTrans2) -- see README.
"""
from __future__ import annotations

from ..schema.models import Operator, Rule

LANGS = {"en": "English", "hi": "हिन्दी"}

# ----------------------------------------------------------------- fields --
FIELD_HI: dict[str, str] = {
    "state": "राज्य",
    "district": "जिला",
    "age": "आयु",
    "gender": "लिंग",
    "social_category": "सामाजिक श्रेणी",
    "is_differently_abled": "दिव्यांग प्रमाणपत्र",
    "land_ha": "भूमि",
    "land_ownership": "भूमि स्वामित्व",
    "farmer_class": "किसान श्रेणी",
    "has_land_records": "भूमि अभिलेख",
    "annual_income": "वार्षिक पारिवारिक आय",
    "is_income_tax_payer": "आयकर दाता",
    "is_govt_employee": "सरकारी कर्मचारी",
    "is_pensioner": "पेंशनभोगी",
    "pension_amount_monthly": "मासिक पेंशन राशि",
    "is_institutional_landholder": "संस्थागत भूमिधारक",
    "crops": "फसलें",
    "livestock": "पशुधन",
    "irrigation_source": "सिंचाई स्रोत",
    "is_organic_farmer": "जैविक किसान",
    "has_kcc": "किसान क्रेडिट कार्ड",
    "has_aadhaar_linked_bank": "आधार से जुड़ा बैंक खाता",
    "has_bank_account": "बैंक खाता",
    "is_bpl": "बीपीएल कार्ड",
    "employment_status": "रोजगार की स्थिति",
    "is_loan_defaulter": "ऋण चूककर्ता",
    "education_level": "शिक्षा स्तर",
    "years_farming": "खेती के वर्ष",
    "residence_type": "निवास क्षेत्र",
    "one_per_family": "परिवार से केवल एक सदस्य",
    "fpo_member": "एफपीओ सदस्य",
    "shg_member": "स्वयं सहायता समूह सदस्य",
    "existing_schemes": "मौजूदा योजनाएँ",
}

# Operator templates. {f} = field, {v} = value. Word order is Hindi's, not a
# transliteration of the English phrasing.
OP_HI: dict[Operator, str] = {
    Operator.EQ: "{f} {v} है",
    Operator.NEQ: "{f} {v} नहीं है",
    Operator.LT: "{f} {v} से कम",
    Operator.LTE: "{f} अधिकतम {v}",
    Operator.GT: "{f} {v} से अधिक",
    Operator.GTE: "{f} कम से कम {v}",
    Operator.IN: "{f} इनमें से एक: {v}",
    Operator.NOT_IN: "{f} इनमें से कोई नहीं: {v}",
    Operator.BETWEEN: "{f} {v} के बीच",
    Operator.EXISTS: "{f} आवश्यक है",
}

UNIT_HI = {"years": "वर्ष", "hectare": "हेक्टेयर", "acre": "एकड़", "INR": "रुपये"}

VALUE_HI: dict[str, str] = {
    # booleans
    "True": "हाँ", "False": "नहीं",
    # gender
    "male": "पुरुष", "female": "महिला", "other": "अन्य",
    # social category
    "SC": "अनुसूचित जाति", "ST": "अनुसूचित जनजाति",
    "OBC": "अन्य पिछड़ा वर्ग", "GENERAL": "सामान्य", "MINORITY": "अल्पसंख्यक",
    # farmer class
    "marginal": "सीमांत", "small": "लघु", "semi_medium": "अर्ध-मध्यम",
    "medium": "मध्यम", "large": "बड़ा",
    # tenure
    "owner": "स्वामी", "tenant": "किरायेदार", "sharecropper": "बटाईदार",
    "landless": "भूमिहीन", "joint": "संयुक्त",
    # residence / employment
    "rural": "ग्रामीण", "urban": "शहरी", "both": "दोनों",
    "unemployed": "बेरोजगार", "salaried": "वेतनभोगी",
    "self_employed": "स्वरोजगार", "govt_employee": "सरकारी कर्मचारी",
    "pensioner": "पेंशनभोगी", "student": "विद्यार्थी",
    # education
    "none": "कोई नहीं", "primary": "प्राथमिक", "class_5": "कक्षा 5",
    "class_8": "कक्षा 8", "class_10": "कक्षा 10", "class_12": "कक्षा 12",
    "graduate": "स्नातक", "technical": "तकनीकी",
}

STATE_HI: dict[str, str] = {
    "ANDHRA_PRADESH": "आंध्र प्रदेश", "ARUNACHAL_PRADESH": "अरुणाचल प्रदेश",
    "ASSAM": "असम", "BIHAR": "बिहार", "CHHATTISGARH": "छत्तीसगढ़",
    "GOA": "गोवा", "GUJARAT": "गुजरात", "HARYANA": "हरियाणा",
    "HIMACHAL_PRADESH": "हिमाचल प्रदेश", "JHARKHAND": "झारखंड",
    "KARNATAKA": "कर्नाटक", "KERALA": "केरल", "MADHYA_PRADESH": "मध्य प्रदेश",
    "MAHARASHTRA": "महाराष्ट्र", "MANIPUR": "मणिपुर", "MEGHALAYA": "मेघालय",
    "MIZORAM": "मिजोरम", "NAGALAND": "नागालैंड", "ODISHA": "ओडिशा",
    "PUNJAB": "पंजाब", "RAJASTHAN": "राजस्थान", "SIKKIM": "सिक्किम",
    "TAMIL_NADU": "तमिलनाडु", "TELANGANA": "तेलंगाना", "TRIPURA": "त्रिपुरा",
    "UTTAR_PRADESH": "उत्तर प्रदेश", "UTTARAKHAND": "उत्तराखंड",
    "WEST_BENGAL": "पश्चिम बंगाल", "ALL": "सभी राज्य",
}


def field_name(f: str, lang: str = "hi") -> str:
    if lang == "en":
        return f.replace("_", " ")
    return FIELD_HI.get(f, f.replace("_", " "))


def value(v, lang: str = "hi") -> str:
    if lang == "en":
        return _en_value(v)
    if isinstance(v, list):
        return ", ".join(value(x, lang) for x in v)
    key = str(v)
    return STATE_HI.get(key) or VALUE_HI.get(key) or key


def _en_value(v) -> str:
    if isinstance(v, list):
        return ", ".join(map(str, v))
    if isinstance(v, bool):
        return "yes" if v else "no"
    return str(v)


def rule_text(rule: Rule, lang: str = "hi") -> str:
    """Render a rule in the requested language."""
    if lang == "en":
        return rule.human()
    f = field_name(rule.field, "hi")
    v = value(rule.value, "hi")
    if rule.unit:
        v = f"{v} {UNIT_HI.get(rule.unit, rule.unit)}"
    return OP_HI[rule.op].format(f=f, v=v).strip()


# Hindi nouns carry grammatical gender and possessives/verbs must agree with
# it: आपकी आयु but आपका राज्य. Hedging with "आपका/आपकी" everywhere reads as
# obviously machine-generated to any Hindi speaker, so gender is recorded per
# field. Fields absent from this set are treated as masculine.
# Gender follows the HEAD NOUN of the Hindi label, not the English field name:
#   has_kcc  -> किसान क्रेडिट कार्ड   (कार्ड, masculine)
#   land_ha  -> भूमि                  (feminine)
# Getting this from the English name produced "आपकी ... कार्ड", which is wrong.
FEMININE: frozenset[str] = frozenset({
    "age",                       # आयु
    "social_category",           # श्रेणी
    "farmer_class",              # श्रेणी
    "land_ha",                   # भूमि
    "annual_income",             # आय
    "crops",                     # फसलें
    "pension_amount_monthly",    # राशि
    "employment_status",         # स्थिति
    "existing_schemes",          # योजनाएँ
})


def check_text(check, lang: str = "hi") -> str:
    """Localised version of Check.explain(), with gender agreement."""
    if lang == "en":
        return check.explain()
    fld = check.rule.field
    f = field_name(fld, "hi")
    cond = rule_text(check.rule, "hi")
    fem = fld in FEMININE
    poss = "आपकी" if fem else "आपका"

    if check.result is None:
        # The auxiliary agrees too: जाननी होगी / जानना होगा.
        verb = "जाननी होगी" if fem else "जानना होगा"
        return f"हमें {poss} {f} {verb}"
    actual = value(check.actual, "hi")
    if check.result:
        verb = "करती" if fem else "करता"
        return f"{poss} {f} ({actual}) शर्त पूरी {verb} है: {cond}"
    return f"{poss} {f} {actual} है, परंतु इस योजना के लिए चाहिए: {cond}"


# --------------------------------------------------------------- UI strings --
UI: dict[str, dict[str, str]] = {
    "title": {"en": "Kisan Mitra", "hi": "किसान मित्र"},
    "tagline": {"en": "Find the government schemes you are eligible for.",
                "hi": "जानिए आप किन सरकारी योजनाओं के पात्र हैं।"},
    "about_you": {"en": "About you", "hi": "आपके बारे में"},
    "about_hint": {"en": "Answer what you can. Blank answers are never held against you.",
                   "hi": "जो बता सकें बताइए। खाली छोड़े गए उत्तर आपके विरुद्ध नहीं जाते।"},
    "sample": {"en": "Try a sample profile", "hi": "नमूना प्रोफ़ाइल आज़माएँ"},
    "own": {"en": "(use my own answers)", "hi": "(मेरे अपने उत्तर)"},
    "q_state": {"en": "Which state do you live in?", "hi": "आप किस राज्य में रहते हैं?"},
    "q_age": {"en": "How old are you?", "hi": "आपकी आयु क्या है?"},
    "q_gender": {"en": "Gender", "hi": "लिंग"},
    "q_income": {"en": "Yearly family income (₹)", "hi": "वार्षिक पारिवारिक आय (₹)"},
    "more": {"en": "More details (optional — unlocks more schemes)",
             "hi": "अधिक जानकारी (वैकल्पिक — और योजनाएँ खुलेंगी)"},
    "not_answered": {"en": "Not answered", "hi": "उत्तर नहीं दिया"},
    "yes": {"en": "Yes", "hi": "हाँ"},
    "no": {"en": "No", "hi": "नहीं"},
    "m_eligible": {"en": "You qualify for", "hi": "आप पात्र हैं"},
    "m_maybe": {"en": "Possibly eligible", "hi": "संभावित रूप से पात्र"},
    "m_not": {"en": "Not eligible", "hi": "पात्र नहीं"},
    "m_answered": {"en": "Questions answered", "hi": "दिए गए उत्तर"},
    "t_eligible": {"en": "Eligible", "hi": "पात्र"},
    "t_need": {"en": "Need more info", "hi": "और जानकारी चाहिए"},
    "t_not": {"en": "Not eligible", "hi": "पात्र नहीं"},
    "why_qualify": {"en": "Why you qualify:", "hi": "आप क्यों पात्र हैं:"},
    "what_you_get": {"en": "What you get:", "hi": "आपको क्या मिलेगा:"},
    "apply": {"en": "Apply / read more", "hi": "आवेदन करें / और पढ़ें"},
    "need_nothing_failed": {"en": "Nothing disqualified you — we just need a few more answers.",
                            "hi": "किसी शर्त ने आपको अयोग्य नहीं ठहराया — बस कुछ और उत्तर चाहिए।"},
    "not_with_reasons": {"en": "Shown with reasons — so you know exactly what ruled you out.",
                         "hi": "कारण सहित — ताकि आपको पता चले कि किस शर्त से आप बाहर हुए।"},
    "start": {"en": "👈 Answer a few questions on the left to see the schemes you qualify for.",
              "hi": "👈 बाईं ओर कुछ प्रश्नों के उत्तर दीजिए और देखिए आप किन योजनाओं के पात्र हैं।"},
    "tip": {"en": "**Tip:** tell us {what} — it would resolve **{n} more scheme(s)**.",
            "hi": "**सुझाव:** हमें {what} बताइए — इससे **{n} और योजनाएँ** स्पष्ट हो जाएँगी।"},
    "no_criteria": {"en": "eligibility not available", "hi": "पात्रता जानकारी उपलब्ध नहीं"},
    "no_criteria_body": {
        "en": "We could not extract this scheme's eligibility rules from the "
              "official page. Check it directly before applying.",
        "hi": "इस योजना की पात्रता शर्तें आधिकारिक पृष्ठ से नहीं निकाली जा सकीं। "
              "आवेदन से पहले सीधे वहाँ जाँच लें।"},
    "prefer_note": {"en": "You also match a preference category — your application may be prioritised.",
                    "hi": "आप वरीयता श्रेणी में भी आते हैं — आपके आवेदन को प्राथमिकता मिल सकती है।"},
    "english_note": {"en": "", "hi": "योजना के नाम और लाभ का विवरण अंग्रेज़ी में हैं "
                                     "(सरकारी पोर्टल से लिया गया)।"},
    "footer": {"en": "Matched against {n} schemes from myscheme.gov.in. Eligibility "
                     "rules are hand-verified but may be out of date — always confirm "
                     "on the official scheme page before applying.",
               "hi": "myscheme.gov.in की {n} योजनाओं से मिलान किया गया। पात्रता शर्तें "
                     "जाँची गई हैं, फिर भी पुरानी हो सकती हैं — आवेदन से पहले आधिकारिक "
                     "पृष्ठ पर पुष्टि अवश्य करें।"},
}


def t(key: str, lang: str = "hi", **fmt) -> str:
    s = UI.get(key, {}).get(lang) or UI.get(key, {}).get("en") or key
    return s.format(**fmt) if fmt else s
