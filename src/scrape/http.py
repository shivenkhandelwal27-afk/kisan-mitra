"""Polite, cached HTTP layer.

Every response is cached to disk keyed by URL hash, so re-running the scraper
costs nothing and government servers are hit exactly once per document. Delete
data/raw/_cache to force a refetch.
"""
from __future__ import annotations

import hashlib, time, logging
from pathlib import Path

import requests

from urllib.parse import urlparse

from ..config import CACHE, USER_AGENT, REQUEST_DELAY_S, REQUEST_TIMEOUT_S

log = logging.getLogger(__name__)

# Per-host courtesy delays. Wikipedia's API explicitly tolerates a steady
# serial rate from an identified client; government portals are small and get
# the conservative default.
_HOST_DELAY = {"en.wikipedia.org": 0.6}
_last_call: dict[str, float] = {}


def _throttle(url: str) -> None:
    host = urlparse(url).netloc
    delay = _HOST_DELAY.get(host, REQUEST_DELAY_S)
    wait = delay - (time.time() - _last_call.get(host, 0.0))
    if wait > 0:
        time.sleep(wait)
    _last_call[host] = time.time()


def get(url: str, params: dict | None = None, binary: bool = False):
    """Fetch a URL, using the on-disk cache when available."""
    CACHE.mkdir(parents=True, exist_ok=True)
    key = hashlib.sha256(f"{url}{sorted((params or {}).items())}".encode()).hexdigest()[:20]
    path = CACHE / (key + (".bin" if binary else ".txt"))
    if path.exists():
        return path.read_bytes() if binary else path.read_text(encoding="utf-8")

    for attempt in range(4):
        _throttle(url)
        log.info("GET %s", url)
        r = requests.get(url, params=params, headers={"User-Agent": USER_AGENT},
                         timeout=REQUEST_TIMEOUT_S)
        if r.status_code == 429:
            back = 2 ** attempt
            log.warning("429 from %s, backing off %ss", urlparse(url).netloc, back)
            time.sleep(back)
            continue
        break
    r.raise_for_status()
    if binary:
        path.write_bytes(r.content); return r.content
    path.write_text(r.text, encoding="utf-8"); return r.text
