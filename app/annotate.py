"""Annotation tool:  streamlit run app/annotate.py

Built for the second-annotator pass. Editing 50 JSONL records by hand is slow
and a single missing comma corrupts the file; here every rule is constructed
through the Rule model, so an invalid field name or an out-of-vocabulary
category is rejected the moment you add it rather than surfacing later as a
mysterious evaluation error.

Progress is written to disk after every change, so closing the tab loses
nothing.

IMPORTANT: this tool never reads or displays the first annotator's labels.
Seeing them would anchor your judgement and inflate the agreement score,
which is the one thing that would make this whole exercise pointless.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.config import GOLD                                    # noqa: E402
from src.schema.fields import FIELDS                           # noqa: E402
from src.schema.models import Operator, Rule                   # noqa: E402

PATH = GOLD / "annotator_b.jsonl"

st.set_page_config(page_title="Annotate", page_icon="✍️", layout="wide")


def load() -> list[dict]:
    return [json.loads(l) for l in open(PATH, encoding="utf-8")]


def save(rows: list[dict]) -> None:
    tmp = PATH.with_suffix(".jsonl.tmp")
    with tmp.open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    tmp.replace(PATH)


if "rows" not in st.session_state:
    st.session_state.rows = load()
    # Resume where you left off rather than restarting at zero.
    done = [i for i, r in enumerate(st.session_state.rows) if r.get("verified")]
    st.session_state.i = (max(done) + 1) if done else 0

rows = st.session_state.rows
n = len(rows)
i = max(0, min(st.session_state.i, n - 1))
row = rows[i]
n_done = sum(1 for r in rows if r.get("verified"))

# ------------------------------------------------------------------ header --
st.progress(n_done / n, text=f"{n_done} of {n} sections done")
c1, c2, c3 = st.columns([1, 1, 6])
if c1.button("← Prev", disabled=i == 0, use_container_width=True):
    st.session_state.i = i - 1
    st.rerun()
if c2.button("Next →", disabled=i >= n - 1, use_container_width=True):
    st.session_state.i = i + 1
    st.rerun()
c3.caption(f"Section {i + 1}/{n} · {row.get('section')} · {row.get('doc', '')[:60]}")

# -------------------------------------------------------------- the text --
st.subheader(row.get("doc", "")[:80])
st.info(row["text"])

st.divider()

# ------------------------------------------------------- existing rules --
left, right = st.columns([3, 2])

with left:
    st.markdown("### Rules you have added")
    if not row["rules"]:
        st.caption("None yet.")
    for k, r in enumerate(list(row["rules"])):
        try:
            human = Rule(**r).human()
        except Exception:
            human = str(r)
        flag = " `[NEG]`" if r.get("negated") else ("" if r.get("mandatory", True) else " `[PREF]`")
        cc1, cc2 = st.columns([8, 1])
        cc1.markdown(f"{k + 1}. {human}{flag}")
        if cc2.button("✕", key=f"del{i}_{k}"):
            row["rules"].pop(k)
            save(rows)
            st.rerun()

with right:
    st.markdown("### Add a rule")
    field = st.selectbox("Field", sorted(FIELDS), key=f"f{i}")
    spec = FIELDS[field]
    st.caption(f"{spec.dtype.value}"
               + (f" · unit: {spec.unit}" if spec.unit else "")
               + (f" · allowed: {', '.join(spec.allowed)}" if spec.allowed else ""))
    op = st.selectbox("Operator", [o.value for o in Operator], key=f"o{i}")

    if spec.allowed and op in ("in", "not_in"):
        raw = st.multiselect("Value", list(spec.allowed), key=f"v{i}")
    elif spec.allowed:
        raw = st.selectbox("Value", list(spec.allowed), key=f"v{i}")
    elif spec.dtype.value == "bool":
        raw = st.radio("Value", [True, False], horizontal=True, key=f"v{i}")
    else:
        raw = st.text_input("Value  (numbers, or comma-separated for lists)",
                            key=f"v{i}")

    unit = st.text_input("Unit (verbatim from the text — acre, years, INR)",
                         value=spec.unit or "", key=f"u{i}")
    neg = st.checkbox("Negated  (text says must NOT / excluded)", key=f"n{i}")
    pref = st.checkbox("Preference only  (not a hard requirement)", key=f"p{i}")

    if st.button("Add rule", type="primary", use_container_width=True):
        v = raw
        if isinstance(raw, str):
            s = raw.strip()
            if "," in s:
                v = [x.strip() for x in s.split(",")]
            else:
                try:
                    v = float(s) if "." in s else int(s)
                except ValueError:
                    v = s
        try:
            # Constructed through the model, so bad values fail HERE.
            rule = Rule(field=field, op=Operator(op), value=v,
                        unit=unit or None, negated=neg, mandatory=not pref)
            row["rules"].append(rule.model_dump(mode="json", exclude_none=True))
            row["no_rules"] = False
            save(rows)
            st.rerun()
        except Exception as e:
            msg = [l for l in str(e).splitlines() if "Value error" in l]
            st.error(msg[0] if msg else str(e)[:300])

st.divider()
b1, b2, b3 = st.columns(3)

if b1.button("✅ Done — has rules", type="primary", use_container_width=True,
             disabled=not row["rules"]):
    row["verified"] = True
    row["no_rules"] = False
    save(rows)
    st.session_state.i = min(i + 1, n - 1)
    st.rerun()

if b2.button("⬜ No rules in this section", use_container_width=True):
    # Valuable negatives: they prove the system does not invent criteria.
    row["rules"] = []
    row["no_rules"] = True
    row["verified"] = True
    save(rows)
    st.session_state.i = min(i + 1, n - 1)
    st.rerun()

if b3.button("🚩 Criterion exists but no field fits", use_container_width=True):
    row["needs_field"] = True
    row["verified"] = True
    save(rows)
    st.session_state.i = min(i + 1, n - 1)
    st.rerun()

with st.sidebar:
    st.header("Reminders")
    st.markdown("""
**One condition per rule.**
"aged 18 to 45" → two rules (`gte 18`, `lte 45`).

**Negation is a flag.**
"must not be a govt employee" →
`is_govt_employee eq False` + tick **Negated**.
Never use `neq`.

**Preference ≠ requirement.**
"preference to women" → tick **Preference only**.

**Never convert units.**
Text says acres → unit `acre`. The code converts.

**Inclusive phrasing is not a rule.**
"all categories are eligible" states no restriction.

**Benefits sections** usually have no rules —
use *No rules*. Those are valuable.
""")
    st.divider()
    st.caption(f"Saving to {PATH.name} after every change.")
    if st.button("Reload from disk"):
        st.session_state.rows = load()
        st.rerun()
