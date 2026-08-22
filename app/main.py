"""Kisan Mitra — scheme eligibility finder.

    streamlit run app/main.py

Design notes, because they are deliberate:

* FOUR questions up front. Rule frequency across the 37 schemes is steep --
  state (26) and age (24) carry half the criteria -- so a farmer gets real
  results after four answers instead of twenty.

* Three buckets, never two. "Not eligible" is shown WITH REASONS rather than
  hidden, because knowing why you failed is actionable and silence is not.

* The "next best question" tip ranks unanswered fields by how many schemes
  each would resolve, turning a long form into a short guided path.

* Hindi is composed, not machine-translated. Explanations are built from a
  translated vocabulary in src/i18n/hindi.py, so they are exact and instant.
  Scheme names and benefit text come from the portal as free-form English and
  are shown as-is, with a note.
"""
from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.i18n.hindi import (LANGS, STATE_HI, check_text, field_name,  # noqa: E402
                            t, value)
from src.match.engine import Verdict, load_schemes, match_all         # noqa: E402
from src.schema.fields import (EMPLOYMENT, GENDERS, LAND_OWNERSHIP,   # noqa: E402
                               RESIDENCE, SOCIAL_CATEGORIES, STATES)

st.set_page_config(page_title="Kisan Mitra", page_icon="🌾", layout="wide")


@st.cache_data
def get_schemes():
    return load_schemes()


def pretty(s: str) -> str:
    return s.replace("_", " ").title()


# --------------------------------------------------------------- language --
lang = st.sidebar.radio("भाषा / Language", list(LANGS),
                        format_func=lambda k: LANGS[k], horizontal=True)

L = lambda k, **f: t(k, lang, **f)          # noqa: E731
opt_none = L("not_answered")


def show_state(code: str) -> str:
    return STATE_HI.get(code, pretty(code)) if lang == "hi" else pretty(code)


def show_val(v) -> str:
    return value(v, lang)


def tri(label: str, key: str) -> bool | None:
    """Yes / No / not-answered. Blank must stay blank.

    A checkbox would silently answer every question 'no' on load, rejecting
    farmers from schemes they qualify for without ever asking them.
    """
    v = st.radio(label, [opt_none, L("yes"), L("no")], horizontal=True, key=key)
    return None if v == opt_none else (v == L("yes"))


st.title(f"🌾 {L('title')}")
st.caption(L("tagline"))

# ---------------------------------------------------------------- sidebar --
with st.sidebar:
    st.header(L("about_you"))
    st.caption(L("about_hint"))

    from src.match.demo import PROFILES as SAMPLES

    own = L("own")
    sample = st.selectbox(L("sample"), [own] + [k.title() for k in SAMPLES])
    locked = sample != own

    profile: dict = {}
    if locked:
        profile = dict(SAMPLES[sample.lower()])
        st.info(f"**{sample}** — {len(profile)} fields")

    state = st.selectbox(L("q_state"),
                         [opt_none] + [show_state(s) for s in STATES if s != "ALL"],
                         disabled=locked)
    if state != opt_none and not locked:
        rev = {show_state(s): s for s in STATES}
        profile["state"] = rev.get(state, state.upper().replace(" ", "_"))

    age = st.number_input(L("q_age"), 0, 120, 0, disabled=locked)
    if age > 0 and not locked:
        profile["age"] = int(age)

    gender = st.selectbox(L("q_gender"), [opt_none] + [show_val(g) for g in GENDERS],
                          disabled=locked)
    if gender != opt_none and not locked:
        profile["gender"] = {show_val(g): g for g in GENDERS}[gender]

    income = st.number_input(L("q_income"), 0, 10_000_000, 0, step=10_000,
                             disabled=locked)
    if income > 0 and not locked:
        profile["annual_income"] = int(income)

    with st.expander(L("more")):
        if not locked:
            for fld, choices in [("social_category", SOCIAL_CATEGORIES),
                                 ("land_ownership", LAND_OWNERSHIP),
                                 ("residence_type", RESIDENCE),
                                 ("employment_status", EMPLOYMENT)]:
                pick = st.selectbox(field_name(fld, lang),
                                    [opt_none] + [show_val(c) for c in choices])
                if pick != opt_none:
                    profile[fld] = {show_val(c): c for c in choices}[pick]

            land = st.number_input(field_name("land_ha", lang) +
                                   (" (हेक्टेयर)" if lang == "hi" else " (hectares)"),
                                   0.0, 100.0, 0.0, step=0.1)
            if land > 0:
                profile["land_ha"] = float(land)

            for fld in ("is_bpl", "has_bank_account", "has_kcc", "is_govt_employee",
                        "is_pensioner", "is_loan_defaulter", "is_differently_abled",
                        "one_per_family"):
                v = tri(field_name(fld, lang), fld)
                if v is not None:
                    profile[fld] = v

# ---------------------------------------------------------------- results --
schemes = get_schemes()

if not profile:
    st.info(L("start"))
    st.stop()

results = match_all(schemes, profile)
elig = [r for r in results if r.verdict is Verdict.ELIGIBLE]
need = [r for r in results if r.verdict is Verdict.NEED_INFO]
nope = [r for r in results if r.verdict is Verdict.NOT_ELIGIBLE]

c1, c2, c3, c4 = st.columns(4)
c1.metric(L("m_eligible"), len(elig))
c2.metric(L("m_maybe"), len(need))
c3.metric(L("m_not"), len(nope))
c4.metric(L("m_answered"), len(profile))

gaps = Counter(f for r in need for f in r.missing_fields)
if gaps:
    top, n = gaps.most_common(1)[0]
    st.success(L("tip", what=field_name(top, lang), n=n))

if lang == "hi":
    st.caption(L("english_note"))

tab1, tab2, tab3 = st.tabs([f"✅ {L('t_eligible')} ({len(elig)})",
                            f"❓ {L('t_need')} ({len(need)})",
                            f"❌ {L('t_not')} ({len(nope)})"])

with tab1:
    for r in elig:
        star = " ⭐" if r.preferences_met else ""
        with st.expander(f"**{r.scheme.name['en']}**{star}", expanded=len(elig) <= 3):
            if r.scheme.benefit_text:
                st.markdown(f"**{L('what_you_get')}** {r.scheme.benefit_text[:400].strip()}")
            st.markdown(f"**{L('why_qualify')}**")
            for c in r.passed:
                st.markdown(f"- {check_text(c, lang)}")
            if r.preferences_met:
                st.markdown(L("prefer_note"))
            st.link_button(L("apply"), r.scheme.apply_url or r.scheme.source_url)

with tab2:
    st.caption(L("need_nothing_failed"))
    for r in need:
        if r.no_criteria:
            with st.expander(f"**{r.scheme.name['en']}** — {L('no_criteria')}"):
                st.markdown(L("no_criteria_body"))
                st.link_button(L("apply"), r.scheme.apply_url or r.scheme.source_url)
            continue
        want = ", ".join(field_name(f, lang) for f in r.missing_fields)
        with st.expander(f"**{r.scheme.name['en']}** — {want}"):
            for c in r.passed:
                st.markdown(f"- ✅ {check_text(c, lang)}")
            for c in r.unknown:
                st.markdown(f"- ❓ {check_text(c, lang)}")
            st.link_button(L("apply"), r.scheme.apply_url or r.scheme.source_url)

with tab3:
    st.caption(L("not_with_reasons"))
    for r in nope:
        with st.expander(f"**{r.scheme.name['en']}**"):
            for c in r.failed:
                st.markdown(f"- ❌ {check_text(c, lang)}")
            st.link_button(L("apply"), r.scheme.apply_url or r.scheme.source_url)

st.divider()
st.caption(L("footer", n=len(schemes)))
