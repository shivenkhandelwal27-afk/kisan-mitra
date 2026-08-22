"""Build the annotation pool:  python -m src.extract.candidates

Turns data/raw/ into data/gold/candidates.jsonl -- one JSON object per
paragraph, ordered so the highest-value paragraphs are annotated first.

Ordering matters. If you annotate in scrape order you spend your first hour on
boilerplate; ordering by eligibility signal means that if you only ever label
150 of 393 paragraphs, those 150 are the informative ones.
"""
from __future__ import annotations

import json, hashlib, re

from ..config import RAW, GOLD
from ..scrape.clean import ELIGIBILITY_CUES

NUMERIC = re.compile(r"\d+(?:\.\d+)?\s*(?:%|hectares?|ha\b|acres?|years?|lakh|crore|₹)", re.I)
NEGATION = re.compile(r"\b(?:not|non-|exclud\w*|ineligib\w*|shall not|should not|except)", re.I)
# Eligibility is always predicated on a person or household. Cost tables are not.
PERSON = re.compile(r"\b(?:farmer|applicant|beneficiar\w*|household|famil\w+|cultivator"
                    r"|his/her|person|individual|owner|tenant|woman|women)", re.I)
# Structural markers of subsidy rate tables: numeric-dense, zero criteria.
TABLE = re.compile(r"(?:cost norms?|pattern of assistance|unit cost|tender|weighted average"
                   r"|per unit|/unit|Sl\.? ?No|@\s*\d+%)", re.I)


# Operational guidelines are mostly about how STATES and INSURERS run a scheme.
# Those clauses match "farmer" incidentally but state no farmer-side criterion,
# and they dominated the ranking until penalised explicitly.
ADMIN = re.compile(r"(?:State Govt|State Government|UT Administration|Insurance Compan"
                   r"|IC|L1|NCIP|Ministry|Department shall|Committee"
                   r"|payment gateway|challan|empanel|allocation|remittance"
                   r"|shall be implemented|monitoring|MIS|portal shall)", re.I)
# Phrasing that marks a genuine farmer-side eligibility clause.
SUBJECT = re.compile(r"(?:farmers?\s+(?:are|is|shall be|who|having|owning|cultivating"
                     r"|covered|eligible)|eligible farmers?|loanee|non-loanee"
                     r"|sharecropper|tenant farmers?|all farmers?)", re.I)


def score(text: str) -> tuple[int, dict]:
    """Annotation priority. Higher = label this sooner.

    Tuned after inspecting the first ranking, which put MIDH cost-norm tables
    and PMFBY tender clauses on top: raw numeric COUNT rewarded dense tables
    stating no criterion about a person. Numerics and negations are now capped
    (presence matters, volume does not), person-reference is weighted heavily,
    and table-shaped text is pushed down.
    """
    cues = len(ELIGIBILITY_CUES.findall(text))
    nums = len(NUMERIC.findall(text))
    negs = len(NEGATION.findall(text))
    persons = len(PERSON.findall(text))
    tables = len(TABLE.findall(text))
    admin = len(ADMIN.findall(text))
    subject = len(SUBJECT.findall(text))
    digit_ratio = sum(c.isdigit() for c in text) / max(len(text), 1)

    total = (min(cues, 4) * 6
             + min(nums, 3) * 2
             + min(negs, 3) * 4
             + min(persons, 4) * 5
             + min(subject, 3) * 12     # explicit farmer-side phrasing
             - min(tables, 4) * 7
             - min(admin, 5) * 6        # institutional plumbing
             - (15 if digit_ratio > 0.10 else 0))
    if cues == 0 and persons == 0:
        total -= 20
    return total, {"cues": cues, "numeric": nums, "negation": negs,
                   "person": persons, "table": tables, "admin": admin,
                   "subject": subject, "digit_ratio": round(digit_ratio, 3)}


def main() -> None:
    GOLD.mkdir(parents=True, exist_ok=True)
    rows, seen = [], set()

    # --- myscheme.gov.in: sections whose heading already tells us what they are
    # No heuristic needed here. A section literally titled "Eligibility" or
    # "Exclusions" on a government scheme page IS eligibility text, so it goes
    # straight to the front of the queue. The scoring function below exists
    # only to guess at unlabelled PDF prose, and guessing is strictly worse
    # than reading the site's own headings.
    SECTION_PRIORITY = {"Eligibility": 1000, "Exclusions": 990, "Benefits": 300}
    mpath = RAW / "myscheme.json"
    if mpath.exists():
        for sec in json.loads(mpath.read_text(encoding="utf-8")).get("sections", []):
            text = sec["text"]
            h = hashlib.sha256(text.encode()).hexdigest()[:16]
            if h in seen or len(text) < 40:
                continue
            seen.add(h)
            _, feats = score(text)
            rows.append({
                "id": h, "text": text,
                "priority": SECTION_PRIORITY.get(sec["section"], 200),
                "features": feats,
                "doc": sec["doc"], "source_url": sec["source_url"],
                "source_type": "myscheme", "section": sec["section"],
                "rules": [], "verified": False, "no_rules": False,
                "needs_field": False, "annotator": None,
            })

    gpath = RAW / "guidelines.json"
    if gpath.exists():
        for rec in json.loads(gpath.read_text(encoding="utf-8"))["records"]:
            for para in rec["eligibility_paragraphs"]:
                h = hashlib.sha256(para.encode()).hexdigest()[:16]
                if h in seen or len(para) < 80:
                    continue
                seen.add(h)
                s, feats = score(para)
                rows.append({
                    "id": h, "text": para, "priority": s, "features": feats,
                    "doc": rec["name"], "source_url": rec["url"],
                    "source_type": "guideline_pdf",
                    # Pre-filled by the Phase 2 extractor; the annotator corrects.
                    "rules": [], "verified": False, "no_rules": False,
                    "needs_field": False, "annotator": None,
                })

    rows.sort(key=lambda r: -r["priority"])
    out = GOLD / "candidates.jsonl"
    with out.open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    top = rows[:250]
    neg = sum(1 for r in top if r["features"]["negation"])
    per = sum(1 for r in top if r["features"]["person"])
    print(f"wrote {out}  ({len(rows)} paragraphs)")
    print(f"  -- within the top-250 annotation target --")
    print(f"  mention a person   : {per:4d}  ({per/max(len(top),1):.0%})")
    print(f"  contain negation   : {neg:4d}  ({neg/max(len(top),1):.0%})")
    print(f"  pool size          : {'MET' if len(rows) >= 250 else f'SHORT by {250-len(rows)}'}")


if __name__ == "__main__":
    main()
