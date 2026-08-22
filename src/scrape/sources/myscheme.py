"""myscheme.gov.in -- the corpus that actually contains farmer eligibility.

WHY THIS EXISTS
The first corpus was built from ministry operational-guideline PDFs (MIDH,
PMFBY, ATMA). Those describe how programmes are ADMINISTERED -- how states
remit premium, how insurers are empanelled -- not which farmer qualifies.
Three independent extractors (regex, qwen2.5:3b, gemini-3.6-flash) each found
about 2 rules per 40 sections on that corpus. The bottleneck was the source
documents, not the models.

myscheme.gov.in is the government's own unified scheme portal. Every scheme
page carries an explicit "Eligibility" section and, crucially, an "Exclusions"
section dense with the negation and threshold phrasing that M1 exists to read:

    "All superannuated/retired pensioners whose monthly pension is
     Rs.10,000/- or more"
    "All Persons who paid Income Tax in last assessment year"

ACCESS METHOD
The site is a client-rendered Next.js app, so plain HTTP returns an empty
shell. Its JSON API requires a key embedded in the frontend, and reusing that
key would mean working around an access control -- so we do not. Instead we
render the public pages in a headless browser exactly as any visitor would,
at a polite request rate, and cache every page to disk so each is fetched once.
robots.txt permits crawling (Disallow: /404 only).
"""
from __future__ import annotations

import json
import logging
import re
import time
from pathlib import Path
from urllib.parse import quote

from ..clean import normalise
from ...config import CACHE

log = logging.getLogger(__name__)

BASE = "https://www.myscheme.gov.in"
CATEGORY = "Agriculture,Rural & Environment"

# The page renders these as headings in order. Splitting innerText on them is
# more durable than CSS selectors, which break whenever the site is restyled.
SECTIONS = [
    "Details", "Benefits", "Eligibility", "Exclusions",
    "Application Process", "Documents Required",
    "Frequently Asked Questions", "Sources And References",
]

# Sections worth annotating. Application Process and FAQ are procedural.
WANTED = ("Eligibility", "Exclusions", "Benefits")

PAGE_WAIT_MS = 8000          # client-side fetch must resolve, not just DOM
NAV_TIMEOUT_MS = 60000       # this connection is slow; 30s was not enough
RENDER_WAIT_S = 25           # max seconds to poll for sections to appear
POLITE_DELAY_S = 1.2


def _cache_path(slug: str) -> Path:
    d = CACHE.parent / "_myscheme"
    d.mkdir(parents=True, exist_ok=True)
    return d / f"{slug}.json"


def split_sections(text: str) -> dict[str, str]:
    """Split a rendered scheme page into its named sections."""
    # Each heading appears TWICE: once in the jump-links nav at the top of the
    # page, then again as the real section heading. Taking the first match
    # split the page across the nav block and yielded empty sections for
    # everything except the last one. The last match is the real heading.
    found: list[tuple[int, str]] = []
    for name in SECTIONS:
        matches = list(re.finditer(rf"^{re.escape(name)}\s*$", text, re.M))
        if matches:
            found.append((matches[-1].start(), name))
    found.sort()

    out: dict[str, str] = {}
    for i, (pos, name) in enumerate(found):
        end = found[i + 1][0] if i + 1 < len(found) else len(text)
        body = text[pos + len(name):end].strip()
        if body:
            out[name] = normalise(body)
    return out


HREFS_JS = "els => els.map(e => e.getAttribute('href'))"

# The agriculture category is the core of the corpus, but the problem statement
# also covers welfare, insurance and credit, and each category browse yields a
# fresh set of schemes. Spanning categories is far more reliable than fighting
# the site's pagination widget.
CATEGORIES = [
    "Agriculture,Rural & Environment",
    "Banking,Financial Services and Insurance",
    "Social welfare & Empowerment",
    "Business & Entrepreneurship",
]


def _visible_slugs(page) -> list[str]:
    hrefs = page.eval_on_selector_all('a[href*="/schemes/"]', HREFS_JS)
    return [h.split("/schemes/")[-1] for h in hrefs if h]


def discover_slugs(page, max_pages: int = 10,
                   categories: list[str] | None = None) -> list[str]:
    """Collect scheme slugs across categories, paginating where possible.

    Pagination is rendered as plain numeric spans that re-render on every
    click, so a locator captured before the click goes stale. We therefore
    re-query the control on each iteration and stop as soon as a click yields
    no new slugs, rather than assuming a fixed page count.
    """
    slugs: list[str] = []
    seen: set[str] = set()

    for cat in (categories or CATEGORIES):
        url = f"{BASE}/search/category/{quote(cat, safe=',')}"
        try:
            # networkidle works on the LISTING page (unlike scheme pages):
            # the results arrive via a client-side fetch well after DOM ready,
            # and reading too early silently returns zero links.
            page.goto(url, wait_until="networkidle", timeout=NAV_TIMEOUT_MS)
            page.wait_for_timeout(PAGE_WAIT_MS)
        except Exception as e:
            log.warning("category %s failed to load: %s", cat, str(e)[:80])
            continue

        for n in range(1, max_pages + 1):
            new = [s for s in _visible_slugs(page) if s not in seen]
            for s in new:
                seen.add(s)
                slugs.append(s)
            log.info("%-42s page %d -> +%d (total %d)", cat[:42], n, len(new), len(slugs))
            if n == max_pages:
                break
            try:
                # Re-query every time; the widget rebuilds after each click.
                page.locator(f'span:text-is("{n + 1}")').last.scroll_into_view_if_needed(
                    timeout=4000)
                page.locator(f'span:text-is("{n + 1}")').last.click(timeout=4000)
                page.wait_for_timeout(5000)
            except Exception:
                log.info("  no page %d control; moving to next category", n + 1)
                break
        time.sleep(POLITE_DELAY_S)

    return slugs


def _render(page, url: str) -> str:
    """Load a scheme page and wait until its sections have actually rendered.

    Scheme pages keep background requests open indefinitely, so `networkidle`
    never fires and goto() times out even though the content arrived long
    before. Wait on the CONTENT instead: poll the rendered text and stop as
    soon as a real section heading appears.
    """
    page.goto(url, wait_until="domcontentloaded", timeout=NAV_TIMEOUT_MS)
    deadline = time.time() + RENDER_WAIT_S
    text, prev_len, stable = "", -1, 0

    while time.time() < deadline:
        try:
            text = page.inner_text("main")
        except Exception:
            text = ""

        # Wait for the text to STOP GROWING, not merely for some headings to
        # appear. An earlier version returned as soon as any two of
        # Details/Benefits/Eligibility were present; sections stream in
        # independently, so on slower loads it captured the page before
        # Eligibility arrived and silently dropped it from 8 of 37 schemes.
        if len(text) == prev_len and len(text) > 500:
            stable += 1
            if stable >= 3:                     # ~1.5s with no growth
                break
        else:
            stable = 0
        prev_len = len(text)
        page.wait_for_timeout(500)

    return text


def fetch_scheme(page, slug: str) -> dict | None:
    """Render one scheme page and return its named sections."""
    cache = _cache_path(slug)
    if cache.exists():
        return json.loads(cache.read_text(encoding="utf-8"))

    url = f"{BASE}/schemes/{slug}"
    try:
        text = _render(page, url)
        # The first line of main is the "Back" control, not the scheme name.
        # The document title carries the real name, which the annotator needs
        # in order to know which scheme a section belongs to.
        page_title = (page.title() or "").strip()
    except Exception as e:
        log.warning("render failed %s: %s", slug, e)
        return None

    sections = split_sections(text)
    if "Eligibility" not in sections:
        log.debug("%s has no Eligibility section", slug)

    title = page_title or slug
    rec = {
        "slug": slug,
        "url": url,
        "title": title,
        "sections": sections,
        "n_chars": len(text),
    }
    cache.write_text(json.dumps(rec, ensure_ascii=False, indent=1), encoding="utf-8")
    time.sleep(POLITE_DELAY_S)
    return rec


def annotatable_sections(rec: dict) -> list[dict]:
    """Flatten a scheme record into individually annotatable chunks."""
    out = []
    for name in WANTED:
        body = rec["sections"].get(name)
        if not body or len(body) < 40:
            continue
        out.append({
            "text": body,
            "section": name,
            "doc": rec["title"][:80],
            "source_url": rec["url"],
        })
    return out


def _launch(pw):
    """Launch a browser, preferring one already on the machine.

    `playwright install chromium` downloads ~150MB from cdn.playwright.dev,
    which failed repeatedly on this connection. Every Windows machine ships
    Edge, and Playwright can drive it directly via the channel argument, so
    we try installed browsers first and fall back to a bundled Chromium only
    if none are present.
    """
    last: Exception | None = None
    for channel in ("msedge", "chrome"):
        try:
            return pw.chromium.launch(headless=True, channel=channel)
        except Exception as e:
            last = e
            log.debug("channel %s unavailable: %s", channel, e)
    try:
        return pw.chromium.launch(headless=True)
    except Exception as e:
        raise RuntimeError(
            "No usable browser. Install Edge or Chrome, or run: "
            "python -m playwright install chromium"
        ) from (last or e)


def run(max_pages: int = 10, max_schemes: int | None = None) -> list[dict]:
    """Full pass: discover slugs, render each scheme, return flat records."""
    from playwright.sync_api import sync_playwright

    records: list[dict] = []
    with sync_playwright() as pw:
        browser = _launch(pw)
        page = browser.new_page(user_agent=(
            "kisan-mitra/0.1 (academic research; contact via project README)"))
        try:
            slugs = discover_slugs(page, max_pages=max_pages)
            if max_schemes:
                slugs = slugs[:max_schemes]
            log.info("fetching %d scheme pages", len(slugs))
            for i, slug in enumerate(slugs, 1):
                rec = fetch_scheme(page, slug)
                if rec:
                    records.append(rec)
                if i % 10 == 0:
                    log.info("  %d/%d", i, len(slugs))
        finally:
            browser.close()
    return records
