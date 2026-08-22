"""Text normalisation shared by every source adapter."""
from __future__ import annotations
import re

# Government PDFs are full of soft hyphens, non-breaking spaces and the
# rupee sign in three different encodings. Normalising early keeps the
# annotation spans stable.
_SUBS = [
    (r"­", ""), (r"[   ]", " "),
    (r"[‘’]", "'"), (r"[“”]", '"'),
    (r"–|—", "-"), (r"Rs\.?\s*", "₹"), (r"INR\s*", "₹"),
]

def normalise(text: str) -> str:
    for pat, rep in _SUBS:
        text = re.sub(pat, rep, text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


ELIGIBILITY_CUES = re.compile(
    r"\b(eligib|beneficiar|criteria|who can apply|qualif|entitled|"
    r"target group|coverage|exclusion|not be|shall not|ineligib)\w*",
    re.I,
)

def eligibility_paragraphs(text: str, window: int = 1) -> list[str]:
    """Pull paragraphs that plausibly state eligibility, plus neighbours.

    Deliberately high-recall: the annotator discards false positives quickly,
    but a criterion that never reaches the candidate pool can never be labelled.
    """
    paras = [p.strip() for p in re.split(r"\n\s*\n", text) if len(p.strip()) > 60]
    hits: set[int] = set()
    for i, p in enumerate(paras):
        if ELIGIBILITY_CUES.search(p):
            hits.update(range(max(0, i - window), min(len(paras), i + window + 1)))
    return [paras[i] for i in sorted(hits)]
