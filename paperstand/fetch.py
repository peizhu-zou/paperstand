"""
fetch.py
Download HTML content from PubMed Central given a PMCID.
"""

import requests
import time
import os
from pathlib import Path

HEADERS = {
    "User-Agent": "PaperStand/1.0 (research tool; contact: your@email.com)"
}

PMC_BASE_URL = "https://www.ncbi.nlm.nih.gov/pmc/articles"


def fetch_html(pmcid: str, delay: float = 1.0) -> str:
    """
    Fetch the HTML of a PubMed Central article by PMCID.

    Args:
        pmcid: PubMed Central ID, e.g. 'PMC1234567' or '1234567'
        delay: seconds to wait before request (polite crawling)

    Returns:
        HTML string of the article page
    """
    # Normalize PMCID format
    if not pmcid.upper().startswith("PMC"):
        pmcid = f"PMC{pmcid}"
    pmcid = pmcid.upper()

    url = f"{PMC_BASE_URL}/{pmcid}/"
    time.sleep(delay)

    response = requests.get(url, headers=HEADERS, timeout=30)
    response.raise_for_status()

    return response.text


def fetch_and_save(pmcid: str, save_dir: str = "data/sample_papers") -> str:
    """
    Fetch HTML and save it to disk. Returns the saved file path.

    Args:
        pmcid: PubMed Central ID
        save_dir: directory to save HTML files

    Returns:
        Path to saved HTML file
    """
    Path(save_dir).mkdir(parents=True, exist_ok=True)

    if not pmcid.upper().startswith("PMC"):
        pmcid = f"PMC{pmcid}"
    pmcid = pmcid.upper()

    save_path = os.path.join(save_dir, f"{pmcid}.html")

    # Skip downloading if already cached
    if os.path.exists(save_path):
        print(f"[fetch] Using cached file: {save_path}")
        with open(save_path, "r", encoding="utf-8") as f:
            return f.read()

    print(f"[fetch] Downloading {pmcid}...")
    html = fetch_html(pmcid)

    with open(save_path, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"[fetch] Saved to {save_path}")
    return html


def fetch_multiple(pmcids: list, save_dir: str = "data/sample_papers", delay: float = 1.5) -> dict:
    """
    Fetch HTML for multiple PMCIDs with polite delay between requests.

    Args:
        pmcids: list of PMCID strings
        save_dir: directory to save HTML files
        delay: seconds between requests

    Returns:
        dict mapping pmcid -> html string
    """
    results = {}
    for pmcid in pmcids:
        try:
            html = fetch_and_save(pmcid, save_dir)
            results[pmcid.upper() if pmcid.upper().startswith("PMC") else f"PMC{pmcid}"] = html
            time.sleep(delay)
        except requests.HTTPError as e:
            print(f"[fetch] ERROR fetching {pmcid}: {e}")
            results[pmcid] = None

    return results


def load_html_from_file(filepath: str) -> str:
    """Load an already-downloaded HTML file from disk."""
    with open(filepath, "r", encoding="utf-8") as f:
        return f.read()
