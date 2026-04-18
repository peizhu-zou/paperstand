"""
fetcher.py
Fetch article HTML from URLs, with disk caching.

Supports:
  - PMC direct download (pmc.ncbi.nlm.nih.gov) — works server-side
  - PLOS direct download (plos.org) — works server-side
  - Any URL with browser-like headers (best-effort)
  - Loading pre-saved HTML files from disk (for Nature, Cell, Science
    which block automated scraping — save from browser with Cmd+S)

Caching:
  Every downloaded HTML is saved to data/html_cache/ by default.
  Re-running the same PMCID or URL skips the network request.
"""

import requests
import time
import os
import re
import hashlib
from pathlib import Path


# ── Constants ─────────────────────────────────────────────────────────────────

PMC_BASE_URL  = "https://pmc.ncbi.nlm.nih.gov/articles"
PLOS_BASE_URL = "https://journals.plos.org"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}

DEFAULT_CACHE_DIR = "data/html_cache"


# ── Public functions ──────────────────────────────────────────────────────────

def fetch_by_pmcid(pmcid: str,
                   cache_dir: str = DEFAULT_CACHE_DIR,
                   delay: float = 1.5) -> tuple[str, str]:
    """
    Fetch a PubMed Central article by PMCID.

    Args:
        pmcid:     e.g. "PMC7012345" or "7012345"
        cache_dir: directory to cache downloaded HTML
        delay:     seconds to wait before each request (be polite)

    Returns:
        (html, url) tuple
    """
    pmcid = _normalize_pmcid(pmcid)
    url   = f"{PMC_BASE_URL}/{pmcid}/"
    html  = _fetch_url(url, cache_key=pmcid, cache_dir=cache_dir, delay=delay)
    return html, url


def fetch_by_url(url: str,
                 cache_dir: str = DEFAULT_CACHE_DIR,
                 delay: float = 1.5) -> tuple[str, str]:
    """
    Fetch an article by its direct URL.
    Works well for PMC and PLOS. Nature/Cell/Science return JS shells
    — for those, save the HTML from your browser and use load_from_file().

    Args:
        url:       full article URL
        cache_dir: directory to cache downloaded HTML
        delay:     seconds to wait before request

    Returns:
        (html, url) tuple
    """
    cache_key = _url_to_cache_key(url)
    html = _fetch_url(url, cache_key=cache_key, cache_dir=cache_dir, delay=delay)
    return html, url


def fetch_batch(items: list,
                cache_dir: str = DEFAULT_CACHE_DIR,
                delay: float = 1.5) -> dict:
    """
    Fetch multiple papers. Each item can be a PMCID string or a URL string.

    Args:
        items:     list of PMCID strings or URL strings
        cache_dir: cache directory
        delay:     seconds between requests

    Returns:
        dict mapping identifier → (html, url) tuple
        Failed fetches map to (None, url).
    """
    results = {}
    for item in items:
        identifier = item
        try:
            if _is_pmcid(item):
                html, url = fetch_by_pmcid(item, cache_dir=cache_dir, delay=delay)
                identifier = _normalize_pmcid(item)
            else:
                html, url = fetch_by_url(item, cache_dir=cache_dir, delay=delay)
            results[identifier] = (html, url)
        except requests.HTTPError as e:
            print(f"[fetcher] ERROR {item}: {e}")
            results[identifier] = (None, item)

    return results


def load_from_file(filepath: str) -> tuple[str, str]:
    """
    Load a pre-saved HTML file from disk.
    Use this for Nature, Cell, Science articles saved from browser.

    Args:
        filepath: path to .html file

    Returns:
        (html, filepath) tuple — filepath used as the URL placeholder
    """
    with open(filepath, "r", encoding="utf-8") as f:
        html = f.read()
    print(f"[fetcher] Loaded {filepath}")
    return html, filepath


def load_from_dir(html_dir: str) -> dict:
    """
    Load all .html files from a directory.

    Args:
        html_dir: path to directory containing .html files

    Returns:
        dict mapping filename_stem → (html, filepath) tuple
        e.g. {"PMC7012345": (html, "data/sample_papers/PMC7012345.html")}
    """
    results = {}
    for fname in sorted(os.listdir(html_dir)):
        if not fname.endswith(".html"):
            continue
        identifier = fname.replace(".html", "")
        fpath      = os.path.join(html_dir, fname)
        html, _    = load_from_file(fpath)
        results[identifier] = (html, fpath)

    if not results:
        print(f"[fetcher] No .html files found in {html_dir}")
    else:
        print(f"[fetcher] Loaded {len(results)} file(s) from {html_dir}")

    return results


# ── Private helpers ───────────────────────────────────────────────────────────

def _normalize_pmcid(pmcid: str) -> str:
    """Ensure PMCID has the 'PMC' prefix."""
    pmcid = pmcid.strip()
    if not pmcid.upper().startswith("PMC"):
        pmcid = f"PMC{pmcid}"
    return pmcid.upper()


def _is_pmcid(s: str) -> bool:
    """Return True if string looks like a PMCID (PMC##### or all digits)."""
    s = s.strip()
    return bool(re.match(r"^PMC\d+$", s, re.IGNORECASE) or re.match(r"^\d{6,}$", s))


def _url_to_cache_key(url: str) -> str:
    """Generate a safe filename from a URL using a short hash."""
    slug = re.sub(r"[^\w\-]", "_", url)[:60]
    h    = hashlib.md5(url.encode()).hexdigest()[:8]
    return f"{slug}_{h}"


def _fetch_url(url: str,
               cache_key: str,
               cache_dir: str,
               delay: float) -> str:
    """
    Core fetch with caching. Returns HTML string.
    Raises requests.HTTPError on non-200 responses.
    """
    Path(cache_dir).mkdir(parents=True, exist_ok=True)
    cache_path = os.path.join(cache_dir, f"{cache_key}.html")

    # Return cached version if available
    if os.path.exists(cache_path):
        print(f"[fetcher] Cache hit: {cache_key}")
        with open(cache_path, "r", encoding="utf-8") as f:
            return f.read()

    # Polite delay before fetching
    print(f"[fetcher] Fetching {url}")
    time.sleep(delay)

    response = requests.get(url, headers=HEADERS, timeout=30)
    response.raise_for_status()
    html = response.text

    # Save to cache
    with open(cache_path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"[fetcher] Cached → {cache_path}")

    return html
