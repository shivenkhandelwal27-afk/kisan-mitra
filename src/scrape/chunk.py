"""Section-aware chunking for government guideline PDFs.

PDF text extraction collapses paragraph breaks, so splitting on blank lines
returned 2,000-3,000 character blobs that mixed unrelated topics -- an
eligibility criterion would sit buried after two pages of technology policy.
That hurt three things at once: the annotator could not see one criterion at a
time, the extractor received mostly irrelevant context, and source spans
pointed into a blob rather than a clause.

These documents are consistently numbered (2.20, 3.1.1, 9.2), so the numbering
is the real document structure. Splitting on it yields topically coherent
units, which is what both the annotator and the model actually need.
"""
from __future__ import annotations

import re

# A section marker: "3.1 ", "2.20 ", "16.4.2 " followed by a capital or bracket.
SECTION = re.compile(r"(?=(?:^|\s)(\d{1,2}(?:\.\d{1,3}){1,3})\s+(?=[A-Z(\"']))")

MIN_CHARS = 90
MAX_CHARS = 1400        # long enough for a full criterion list, short enough to read


def split_sections(text: str) -> list[str]:
    """Split a guideline document into numbered sections."""
    # SECTION is a lookahead with a capture group, so split() emits the clause
    # number twice: once as its own element, once at the head of the body that
    # follows. Drop the standalone copies rather than re-attaching them.
    parts = [p.strip() for p in SECTION.split(text) if p and p.strip()]
    out = [p for p in parts
           if not re.fullmatch(r"\d{1,2}(?:\.\d{1,3}){1,3}", p)]

    # Oversized sections (usually un-numbered tables) are split on sentences.
    chunks: list[str] = []
    for c in out:
        if len(c) <= MAX_CHARS:
            chunks.append(c)
            continue
        buf = ""
        for sent in re.split(r"(?<=[.;])\s+", c):
            if len(buf) + len(sent) > MAX_CHARS and buf:
                chunks.append(buf.strip())
                buf = ""
            buf += sent + " "
        if buf.strip():
            chunks.append(buf.strip())

    return [c for c in chunks if len(c) >= MIN_CHARS]
