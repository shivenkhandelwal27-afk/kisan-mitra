"""Discovery source.

Wikipedia is used to ENUMERATE schemes and capture their descriptions -- not
as an eligibility source. Spot-checking showed major scheme articles (PM-KISAN
included) carry history and statistics but no eligibility criteria, so the
rules come from the guideline PDFs instead. Keeping the roles separate is
deliberate: discovery wants breadth, extraction wants authority.
"""
from __future__ import annotations

import json, logging

from ..http import get
from ..clean import normalise
from ...config import TARGET_STATES

log = logging.getLogger(__name__)
API = "https://en.wikipedia.org/w/api.php"

ROOT_CATEGORY = "Category:Government_schemes_in_India"
# Only pull state subcategories we actually target, plus the always-relevant ones.
ALWAYS = {"Category:Social_security_in_India", "Category:Indian_missions"}


def _api(**params) -> dict:
    params.setdefault("format", "json")
    return json.loads(get(API, params=params))


def _members(category: str, kind: str) -> list[str]:
    out, cont = [], {}
    while True:
        d = _api(action="query", list="categorymembers", cmtitle=category,
                 cmlimit="500", cmtype=kind, **cont)
        out += [m["title"] for m in d.get("query", {}).get("categorymembers", [])]
        if "continue" not in d:
            return out
        cont = d["continue"]


def discover_titles() -> list[str]:
    """Scheme article titles from the root category and targeted subcategories."""
    titles = set(_members(ROOT_CATEGORY, "page"))
    subcats = _members(ROOT_CATEGORY, "subcat")
    wanted = {c for c in subcats
              if c in ALWAYS
              or any(st.replace("_", " ").title() in c.replace("_", " ")
                     for st in TARGET_STATES)}
    for c in sorted(wanted):
        found = _members(c, "page")
        log.info("subcategory %s -> %d", c, len(found))
        titles.update(found)
    return sorted(titles)


BATCH = 20   # MediaWiki caps exlimit at 20 for anonymous clients


def fetch_extracts(titles: list[str]) -> list[dict]:
    """Fetch article extracts in batches.

    One request per 20 titles rather than per title: 130 articles cost 7
    requests instead of 130, which keeps us comfortably inside Wikipedia's
    rate limits instead of triggering 429s.
    """
    out: list[dict] = []
    for i in range(0, len(titles), BATCH):
        chunk = titles[i:i + BATCH]
        # exintro is required for batching: MediaWiki silently enforces
        # exlimit=1 when full extracts are requested, so without it only the
        # first title in each batch comes back populated. Intro text is what
        # discovery needs anyway -- eligibility comes from the guideline PDFs.
        d = _api(action="query", prop="extracts|info", explaintext="1",
                 exintro="1", exlimit=str(BATCH), inprop="url",
                 titles="|".join(chunk))
        for page in d.get("query", {}).get("pages", {}).values():
            out.append({
                "title": page.get("title", ""),
                "text": normalise(page.get("extract", "") or ""),
                "url": page.get("fullurl", ""),
            })
        log.info("  extracts %d/%d", min(i + BATCH, len(titles)), len(titles))
    return out
