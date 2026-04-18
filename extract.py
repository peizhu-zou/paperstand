"""
extract.py
Extract specific standardized fields from a parsed paper dict.
Handles variation in section naming across journals.
"""

import re

# ── Section name aliases ─────────────────────────────────────────────────────
# Maps canonical field name -> list of possible heading variants
SECTION_ALIASES = {
    "introduction": ["introduction", "background", "overview"],
    "methods": [
        "methods", "materials and methods", "methodology",
        "experimental procedures", "patients and methods",
        "subjects and methods", "experimental design",
        "materials & methods", "methods and materials",
    ],
    "results": ["results", "findings", "outcomes"],
    "discussion": ["discussion", "interpretation"],
    "conclusion": ["conclusion", "conclusions", "concluding remarks", "summary"],
    "data_availability": [
        "data availability", "data availability statement",
        "availability of data", "data and code availability",
        "availability of data and materials",
        "data sharing", "code availability",
    ],
    "funding": ["funding", "financial support", "funding sources", "acknowledgements of funding"],
    "acknowledgements": ["acknowledgements", "acknowledgments", "acknowledgment"],
    "ethics": ["ethics", "ethics statement", "ethical approval", "ethics declarations"],
    "supplementary": ["supplementary", "supplementary material", "supplemental information"],
    "conflict_of_interest": [
        "conflict of interest", "competing interests",
        "conflicts of interest", "declaration of competing interests",
    ],
    "author_contributions": ["author contributions", "contributions", "authors' contributions"],
}


def extract_fields(paper: dict) -> dict:
    """
    Extract all standardized fields from a parsed paper dict.

    Args:
        paper: nested dict from parse.parse_paper()

    Returns:
        Flat dict of extracted fields ready for spreadsheet export
    """
    sections = paper.get("sections", {})
    metadata = paper.get("metadata", {})

    record = {
        # Identifiers
        "pmcid": paper.get("pmcid", ""),
        "doi": metadata.get("doi", ""),

        # Bibliographic
        "title": paper.get("title", ""),
        "authors": "; ".join(metadata.get("authors", [])),
        "journal": metadata.get("journal", ""),
        "date": metadata.get("date", ""),
        "keywords": "; ".join(metadata.get("keywords", [])),

        # Abstract
        "abstract": paper.get("abstract", ""),

        # Body sections (resolved by alias)
        "introduction": _resolve_section(sections, "introduction"),
        "methods": _resolve_section(sections, "methods"),
        "results": _resolve_section(sections, "results"),
        "discussion": _resolve_section(sections, "discussion"),
        "conclusion": _resolve_section(sections, "conclusion"),
        "data_availability": _resolve_section(sections, "data_availability"),
        "funding": _resolve_section(sections, "funding"),
        "acknowledgements": _resolve_section(sections, "acknowledgements"),
        "ethics": _resolve_section(sections, "ethics"),
        "conflict_of_interest": _resolve_section(sections, "conflict_of_interest"),
        "author_contributions": _resolve_section(sections, "author_contributions"),

        # Figures / tables
        "n_figures": len(paper.get("figures", [])),
        "n_tables": len(paper.get("tables", [])),
        "n_references": len(paper.get("references", [])),

        # Raw section headings found (for debugging)
        "section_headings_found": "; ".join(sections.keys()),
    }

    return record


def _resolve_section(sections: dict, canonical_name: str) -> str:
    """
    Look up a section by its canonical name using the alias table.
    Case-insensitive matching.

    Args:
        sections: dict of {heading: text} from parser
        canonical_name: key in SECTION_ALIASES

    Returns:
        Section text or empty string if not found
    """
    aliases = SECTION_ALIASES.get(canonical_name, [canonical_name])
    sections_lower = {k.lower().strip(): v for k, v in sections.items()}

    for alias in aliases:
        if alias.lower() in sections_lower:
            return sections_lower[alias.lower()]

    # Partial match fallback
    for alias in aliases:
        for heading_lower, text in sections_lower.items():
            if alias.lower() in heading_lower or heading_lower in alias.lower():
                return text

    return ""


def extract_accession_codes(text: str) -> list:
    """
    Extract common genomic/bioinformatic accession codes from text.
    Useful for the stretch goal.

    Patterns covered:
        GEO: GSE####, GSM####, GPL####
        SRA: SRP####, SRR####, SRX####, PRJNA####
        ENA: ERP####, ERR####, ERX####, PRJEB####
        ArrayExpress: E-MTAB-####
        dbGaP: phs####
        Zenodo: zenodo.####
    """
    patterns = {
        "GEO_series":       r"\bGSE\d+\b",
        "GEO_sample":       r"\bGSM\d+\b",
        "GEO_platform":     r"\bGPL\d+\b",
        "SRA_study":        r"\bSRP\d+\b",
        "SRA_run":          r"\bSRR\d+\b",
        "SRA_experiment":   r"\bSRX\d+\b",
        "BioProject_NCBI":  r"\bPRJNA\d+\b",
        "ENA_project":      r"\bERP\d+\b",
        "ENA_run":          r"\bERR\d+\b",
        "BioProject_ENA":   r"\bPRJEB\d+\b",
        "ArrayExpress":     r"\bE-MTAB-\d+\b",
        "dbGaP":            r"\bphs\d{6}\.v\d+\.p\d+\b|\bphs\d+\b",
        "Zenodo":           r"\bzenodo\.\d+\b",
    }

    found = {}
    for name, pattern in patterns.items():
        matches = re.findall(pattern, text, re.IGNORECASE)
        if matches:
            found[name] = list(set(matches))

    return found


def extract_fields_multiple(papers: dict) -> list:
    """
    Extract fields from multiple parsed papers.

    Args:
        papers: dict mapping pmcid -> parsed paper dict

    Returns:
        List of flat record dicts (one per paper)
    """
    records = []
    for pmcid, paper in papers.items():
        print(f"[extract] Extracting fields from {pmcid}...")
        record = extract_fields(paper)
        records.append(record)
    return records
