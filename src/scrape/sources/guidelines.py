"""Authoritative eligibility source: official operational-guideline PDFs.

These are the documents the M1 model is trained to read. They state eligibility
in full prose -- with negation ("shall not be"), mixed units (acre vs hectare),
and conditions nested across clauses -- which is precisely what makes the
extraction task non-trivial and the project worth doing.
"""
from __future__ import annotations

import io, logging
from urllib.parse import urljoin

from bs4 import BeautifulSoup
from pypdf import PdfReader

from ..http import get
from ..clean import normalise, ELIGIBILITY_CUES
from ..chunk import split_sections

log = logging.getLogger(__name__)

# Index pages that list guideline PDFs. Add state agriculture departments here.
# Two document types, deliberately kept separate.
#
# The agriwelfare "Major"/"Schemes" PDFs are OPERATIONAL GUIDELINES written for
# state governments: cost norms, empanelment, remittance. Inspection found only
# 10 eligibility-section headings across 12 such documents, and those list
# eligible ENTITY TYPES (individuals, FPOs, NGOs) rather than farmer attributes.
#
# pmkisan.gov.in carries the farmer-facing documents -- scheme guidelines with
# exclusion categories, and FAQs in "who is eligible" Q&A form. Those are where
# land-size, age, income-tax and pension criteria actually live, so they are the
# real M1 training material.
INDEX_PAGES = [
    "https://pmkisan.gov.in/",              # farmer-facing: OG, FAQs, PM-KMY, KCC
    "https://agriwelfare.gov.in/en/Major",
    "https://agriwelfare.gov.in/en/Schemes",
]

# Scheme portals whose guidelines are not linked from the ministry index.
# Add state agriculture department guideline PDFs here as you find them.
# (Two earlier entries were dropped: both URLs now serve HTML redirects, and
# the PMFBY guidelines arrive via the ministry index regardless.)
EXTRA_PDFS: list[str] = []


def discover_pdfs() -> list[str]:
    urls: set[str] = set()
    for index in INDEX_PAGES:
        try:
            html = get(index)
        except Exception as e:
            log.warning("index %s failed: %s", index, e)
            continue
        soup = BeautifulSoup(html, "lxml")
        for a in soup.find_all("a", href=True):
            if ".pdf" in a["href"].lower():
                urls.add(urljoin(index, a["href"]))
    urls.update(EXTRA_PDFS)
    return sorted(urls)


def pdf_text(url: str, max_pages: int = 60) -> str:
    """Extract text from a guideline PDF.

    Capped at max_pages: guideline documents run to hundreds of pages, but
    eligibility is stated early, and unbounded extraction buries the annotator.
    """
    raw = get(url, binary=True)
    reader = PdfReader(io.BytesIO(raw))
    pages = [(p.extract_text() or "") for p in reader.pages[:max_pages]]
    return normalise("\n\n".join(pages))


def fetch(url: str) -> dict | None:
    try:
        text = pdf_text(url)
    except Exception as e:
        log.warning("pdf failed %s: %s", url, e)
        return None
    if len(text) < 400:          # scanned/image-only PDF -> needs OCR, skip for now
        log.warning("pdf too short (likely scanned): %s", url)
        return None
    # Section-aware chunking, then keep sections that plausibly state
    # eligibility. High recall on purpose: the annotator discards false
    # positives fast, but a criterion never surfaced can never be labelled.
    sections = split_sections(text)
    paras = [s for s in sections if ELIGIBILITY_CUES.search(s)]
    return {
        "url": url,
        "name": url.rsplit("/", 1)[-1].replace(".pdf", "").replace("_", " "),
        "full_text": text,
        "eligibility_paragraphs": paras,
        "n_chars": len(text),
        "n_sections": len(sections),
    }
