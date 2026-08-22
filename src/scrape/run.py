"""Phase 1 entry point:  python -m src.scrape.run

Builds data/raw/ from two complementary sources and reports corpus statistics.
Safe to re-run: every fetch is disk-cached.
"""
from __future__ import annotations

import json, logging, re, sys
from datetime import date

from ..config import RAW, TARGET_STATES
from .sources import wikipedia, guidelines

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s",
                    stream=sys.stdout)
log = logging.getLogger("scrape")

# Used only to rank annotation priority, never to drop documents -- the problem
# statement covers welfare and insurance too, not just crop schemes.
AGRI_TERMS = re.compile(
    r"\b(farmer|agricultur|crop|kisan|rythu|krishi|irrigation|horticultur|"
    r"soil|seed|fertilis|fertiliz|dairy|livestock|fisher|land|rural|"
    r"insurance|credit|loan|subsid)\w*", re.I)


def agri_score(text: str) -> int:
    return len(AGRI_TERMS.findall(text or ""))


def run_wikipedia() -> list[dict]:
    titles = wikipedia.discover_titles()
    log.info("discovered %d wikipedia titles", len(titles))
    out = []
    for rec in wikipedia.fetch_extracts(titles):
        if len(rec["text"]) < 120:      # stubs and redirects
            continue
        rec["agri_score"] = agri_score(rec["text"])
        rec["source"] = "wikipedia"
        out.append(rec)
    return out


def run_guidelines() -> list[dict]:
    urls = guidelines.discover_pdfs()
    log.info("discovered %d guideline PDFs", len(urls))
    out = []
    for u in urls:
        rec = guidelines.fetch(u)
        if not rec:
            continue
        rec["agri_score"] = agri_score(rec["full_text"])
        rec["source"] = "guideline_pdf"
        out.append(rec)
        log.info("  %-52s %6d chars  %2d elig-paras",
                 rec["name"][:52], rec["n_chars"], len(rec["eligibility_paragraphs"]))
    return out


def main() -> None:
    RAW.mkdir(parents=True, exist_ok=True)

    wiki = run_wikipedia()
    (RAW / "wikipedia.json").write_text(
        json.dumps({"generated_at": str(date.today()), "states": TARGET_STATES,
                    "records": wiki}, ensure_ascii=False, indent=1), encoding="utf-8")

    guide = run_guidelines()
    (RAW / "guidelines.json").write_text(
        json.dumps({"generated_at": str(date.today()), "records": guide},
                   ensure_ascii=False, indent=1), encoding="utf-8")

    n_paras = sum(len(g["eligibility_paragraphs"]) for g in guide)
    print("\n" + "=" * 62)
    print(f"  wikipedia records      : {len(wiki)}")
    print(f"  guideline PDFs         : {len(guide)}")
    print(f"  eligibility paragraphs : {n_paras}   <- M1 annotation pool")
    print(f"  target states          : {', '.join(TARGET_STATES)}")
    print("=" * 62)
    if n_paras < 250:
        print(f"  NOTE: {n_paras} paragraphs is below the 250 gold-set target.")
        print("        Add state agriculture dept PDFs to guidelines.INDEX_PAGES.")


if __name__ == "__main__":
    main()
