"""
extractor.py
Extract standardized flat fields from a parsed paper dict.

The parsers return raw section text under the original headings
(e.g. "Materials and Methods", "METHODS", "Experimental Procedures").
This module resolves all those variants to canonical field names
(e.g. "methods") so the output is consistent across journals.
"""

# ── Section alias table ───────────────────────────────────────────────────────
# Maps canonical field name → list of accepted heading variants (lowercased)
# Matching is case-insensitive. Partial matches are tried as a fallback.

SECTION_ALIASES = {
    "introduction": [
        "introduction", "background", "overview",
    ],
    "methods": [
        "methods", "materials and methods", "materials & methods",
        "methods and materials", "methodology", "experimental procedures",
        "experimental methods", "patients and methods", "subjects and methods",
        "experimental design", "star methods", "resource availability",
    ],
    "results": [
        "results", "findings", "outcomes", "results and discussion",
    ],
    "discussion": [
        "discussion", "interpretation", "results and discussion",
    ],
    "conclusion": [
        "conclusion", "conclusions", "concluding remarks",
        "summary", "perspectives",
    ],
    "data_availability": [
        "data availability", "data availability statement",
        "availability of data", "data and code availability",
        "availability of data and materials", "data sharing",
        "code availability", "data and software availability",
        "data access", "data deposition",
    ],
    "funding": [
        "funding", "financial support", "funding sources",
        "acknowledgements of funding", "funding information",
        "financial support and sponsorship",
    ],
    "acknowledgements": [
        "acknowledgements", "acknowledgments", "acknowledgment",
    ],
    "ethics": [
        "ethics", "ethics statement", "ethical approval",
        "ethics declarations", "ethical considerations",
        "institutional review", "compliance with ethical standards",
    ],
    "conflict_of_interest": [
        "conflict of interest", "competing interests",
        "conflicts of interest", "declaration of competing interests",
        "competing financial interests", "disclosures",
    ],
    "author_contributions": [
        "author contributions", "contributions",
        "authors' contributions", "author information",
    ],
    "supplementary": [
        "supplementary", "supplementary material",
        "supplemental information", "supporting information",
        "extended data",
    ],
}


# ── Public functions ──────────────────────────────────────────────────────────

def extract(paper: dict) -> dict:
    """
    Extract all standardized fields from a parsed paper dict.

    Args:
        paper: nested dict returned by any parser's .parse() method

    Returns:
        Flat dict with one key per field, ready for export or NLP enrichment
    """
    sections = paper.get("sections", {})
    metadata = paper.get("metadata", {})

    record = {
        # ── Identifiers ───────────────────────────────────────────────────────
        "identifier": paper.get("identifier", ""),
        "url":        paper.get("url", ""),
        "doi":        metadata.get("doi", ""),

        # ── Bibliographic ─────────────────────────────────────────────────────
        "title":    paper.get("title", ""),
        "authors":  "; ".join(metadata.get("authors", [])),
        "journal":  metadata.get("journal", ""),
        "date":     metadata.get("date", ""),
        "keywords": "; ".join(metadata.get("keywords", [])),

        # ── Content ───────────────────────────────────────────────────────────
        "abstract":           paper.get("abstract", ""),
        "introduction":       _resolve(sections, "introduction"),
        "methods":            _resolve(sections, "methods"),
        "results":            _resolve(sections, "results"),
        "discussion":         _resolve(sections, "discussion"),
        "conclusion":         _resolve(sections, "conclusion"),
        "data_availability":  _resolve(sections, "data_availability"),
        "funding":            _resolve(sections, "funding"),
        "acknowledgements":   _resolve(sections, "acknowledgements"),
        "ethics":             _resolve(sections, "ethics"),
        "conflict_of_interest":  _resolve(sections, "conflict_of_interest"),
        "author_contributions":  _resolve(sections, "author_contributions"),

        # ── Counts ────────────────────────────────────────────────────────────
        "n_figures":    len(paper.get("figures",    [])),
        "n_tables":     len(paper.get("tables",     [])),
        "n_references": len(paper.get("references", [])),

        # ── Debug ─────────────────────────────────────────────────────────────
        # Useful for spotting which headings a new journal uses
        "section_headings_found": "; ".join(sections.keys()),
    }

    return record


def extract_many(papers: dict) -> list:
    """
    Extract fields from multiple parsed papers.

    Args:
        papers: dict mapping identifier → parsed paper dict

    Returns:
        List of flat record dicts (one per paper)
    """
    records = []
    for identifier, paper in papers.items():
        print(f"[extractor] Extracting {identifier}...")
        records.append(extract(paper))
    return records


# ── Private helpers ───────────────────────────────────────────────────────────

def _resolve(sections: dict, canonical_name: str) -> str:
    """
    Resolve a canonical field name to section text using the alias table.

    Matching strategy (in order):
      1. Exact match (case-insensitive)
      2. Partial match — alias is a substring of heading, or vice versa

    Args:
        sections:       {heading: text} dict from parser
        canonical_name: key in SECTION_ALIASES

    Returns:
        Section text, or empty string if not found
    """
    aliases = SECTION_ALIASES.get(canonical_name, [canonical_name])
    sections_lower = {k.lower().strip(): v for k, v in sections.items()}

    # 1. Exact match
    for alias in aliases:
        if alias in sections_lower:
            return sections_lower[alias]

    # 2. Partial match
    for alias in aliases:
        for heading, text in sections_lower.items():
            if alias in heading or heading in alias:
                return text

    return ""
