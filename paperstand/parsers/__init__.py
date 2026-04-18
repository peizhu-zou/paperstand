"""
parsers/__init__.py
Router — detects journal from URL or HTML meta tags,
returns the correct parser instance.

Detection priority:
  1. URL pattern  (most reliable — use whenever available)
  2. <meta name="citation_journal_title"> content
  3. <meta property="og:site_name"> content
  4. GenericParser fallback (always succeeds, logs a warning)
"""

import re
from bs4 import BeautifulSoup

from .base    import BaseParser
from .pmc     import PMCParser
from .nature  import NatureParser
from .cell    import CellParser
from .science import ScienceParser
from .plos    import PLOSParser
from .generic import GenericParser


# ── URL routing ───────────────────────────────────────────────────────────────
# Checked in order — first match wins
URL_RULES = [
    (re.compile(r"pmc\.ncbi\.nlm\.nih\.gov|ncbi\.nlm\.nih\.gov/pmc"), PMCParser),
    (re.compile(r"nature\.com"),                                        NatureParser),
    (re.compile(r"cell\.com"),                                          CellParser),
    (re.compile(r"science\.org|sciencemag\.org"),                       ScienceParser),
    (re.compile(r"plos\.org|plosbiology|plosone|plosgenetics|"
                r"ploscompbiol|plosmedicine|plospathogens"),            PLOSParser),
]

# ── Meta tag routing ──────────────────────────────────────────────────────────
# Used when URL is empty (e.g. loaded from local HTML file)
# Key = substring to match in journal name (lowercased)
META_RULES = [
    ("pubmed central",              PMCParser),
    ("nature",                      NatureParser),   # catches Nature, Nat Commun, etc.
    ("cell",                        CellParser),     # catches Cell, Cell Reports, etc.
    ("current biology",             CellParser),
    ("immunity",                    CellParser),
    ("neuron",                      CellParser),
    ("science",                     ScienceParser),  # catches Science, Sci Adv, etc.
    ("plos",                        PLOSParser),
]


def get_parser(html: str, url: str = "", identifier: str = "unknown") -> BaseParser:
    """
    Detect journal and return the correct parser instance.

    Args:
        html:       raw HTML string of the article page
        url:        source URL (used for routing when available)
        identifier: PMCID, DOI slug, or any ID string

    Returns:
        Instantiated parser — call .parse() to get the paper dict
    """
    # 1. URL-based routing
    url_lower = url.lower()
    for pattern, parser_class in URL_RULES:
        if pattern.search(url_lower):
            return parser_class(html, url=url, identifier=identifier)

    # 2. Meta tag routing (for locally loaded HTML files)
    soup = BeautifulSoup(html, "lxml")

    journal_name = ""
    for meta_name in ["citation_journal_title", "citation_publisher"]:
        tag = soup.find("meta", attrs={"name": meta_name})
        if tag and tag.get("content"):
            journal_name = tag["content"].lower()
            break

    if not journal_name:
        tag = soup.find("meta", attrs={"property": "og:site_name"})
        if tag:
            journal_name = tag.get("content", "").lower()

    for keyword, parser_class in META_RULES:
        if keyword in journal_name:
            return parser_class(html, url=url, identifier=identifier)

    # 3. Fallback
    return GenericParser(html, url=url, identifier=identifier)


def detect_journal_name(url: str = "", html: str = "") -> str:
    """Return a human-readable journal name for logging."""
    url_lower = url.lower()
    labels = [
        (r"pmc\.ncbi|ncbi\.nlm.*pmc", "PMC"),
        (r"nature\.com",               "Nature"),
        (r"cell\.com",                 "Cell Press"),
        (r"science\.org|sciencemag",   "Science"),
        (r"plos\.org",                 "PLOS"),
    ]
    for pattern, label in labels:
        if re.search(pattern, url_lower):
            return label
    return "Unknown"
