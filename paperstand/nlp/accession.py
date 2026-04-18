"""
nlp/accession.py
Extract data repository accession codes and URLs from paper text.

Handles:
  GEO        — GSE######, GSM######, GPL######
  SRA        — SRP######, SRR######, SRX######
  BioProject — PRJNA######, PRJEB######
  ENA        — ERP######, ERR######, ERX######
  ArrayExpress — E-MTAB-######
  dbGaP      — phs######
  Zenodo     — zenodo.######
  ProteomeXchange — PXD######
  GSA (China) — HRA######, CRA######

Also extracts:
  - Raw URLs from data availability statements
  - Repository names (GEO, BioProject, GitHub, etc.)
"""

import re


# ── Accession code patterns ───────────────────────────────────────────────────

ACCESSION_PATTERNS = {
    "GEO_series":         r"\bGSE\d+\b",
    "GEO_sample":         r"\bGSM\d+\b",
    "GEO_platform":       r"\bGPL\d+\b",
    "SRA_study":          r"\bSRP\d+\b",
    "SRA_run":            r"\bSRR\d+\b",
    "SRA_experiment":     r"\bSRX\d+\b",
    "BioProject_NCBI":    r"\bPRJNA\d+\b",
    "BioProject_ENA":     r"\bPRJEB\d+\b",
    "ENA_project":        r"\bERP\d+\b",
    "ENA_run":            r"\bERR\d+\b",
    "ENA_experiment":     r"\bERX\d+\b",
    "ArrayExpress":       r"\bE-MTAB-\d+\b",
    "dbGaP":              r"\bphs\d{6}(?:\.v\d+\.p\d+)?\b",
    "Zenodo":             r"\bzenodo\.\d+\b",
    "ProteomeXchange":    r"\bPXD\d+\b",
    "GSA_HRA":            r"\bHRA\d+\b",
    "GSA_CRA":            r"\bCRA\d+\b",
}

# Repository URL substrings → human-readable label
REPO_URL_MAP = {
    "ncbi.nlm.nih.gov/geo":         "GEO",
    "ncbi.nlm.nih.gov/bioproject":  "BioProject",
    "ncbi.nlm.nih.gov/sra":         "SRA",
    "ncbi.nlm.nih.gov/dbgap":       "dbGaP",
    "ebi.ac.uk/arrayexpress":        "ArrayExpress",
    "ebi.ac.uk/ena":                 "ENA",
    "proteomexchange.org":           "ProteomeXchange",
    "pride.ebi.ac.uk":               "PRIDE",
    "zenodo.org":                    "Zenodo",
    "figshare.com":                  "figshare",
    "github.com":                    "GitHub",
    "dryad":                         "Dryad",
    "mendeley":                      "Mendeley Data",
    "osf.io":                        "OSF",
    "synapse.org":                   "Synapse",
    "ngdc.cncb.ac.cn":               "GSA (China)",
    "cncb.ac.cn":                    "GSA (China)",
}

# Text keyword → label (catches mentions without a URL)
REPO_TEXT_MAP = {
    "GEO":              r"\bGEO\b|\bGene Expression Omnibus\b",
    "SRA":              r"\bSRA\b|\bSequence Read Archive\b",
    "BioProject":       r"\bBioProject\b",
    "ArrayExpress":     r"\bArrayExpress\b",
    "Zenodo":           r"\bZenodo\b",
    "figshare":         r"\bfigshare\b",
    "GitHub":           r"\bGitHub\b",
    "Dryad":            r"\bDryad\b",
    "dbGaP":            r"\bdbGaP\b",
    "OSF":              r"\bOpen Science Framework\b|\bOSF\b",
    "Synapse":          r"\bSynapse\b",
    "ProteomeXchange":  r"\bProteomeXchange\b|\bPXD\b",
    "PRIDE":            r"\bPRIDE\b",
    "GSA":              r"\bGSA\b|\bGenome Sequence Archive\b",
}


# ── Public functions ──────────────────────────────────────────────────────────

def extract_accession_codes(text: str) -> dict:
    """
    Extract all accession codes from text.

    Args:
        text: any string (data availability statement, methods section, etc.)

    Returns:
        dict mapping database name → list of found codes
        e.g. {"GEO_series": ["GSE123456"], "BioProject_NCBI": ["PRJNA805052"]}
    """
    found = {}
    for db_name, pattern in ACCESSION_PATTERNS.items():
        matches = re.findall(pattern, text, re.IGNORECASE)
        if matches:
            found[db_name] = list(set(matches))
    return found


def extract_data_availability(text: str) -> dict:
    """
    Full parse of a data availability statement.
    Extracts URLs, repository names, and accession codes.

    Args:
        text: data availability section text

    Returns:
        {
            "urls":             ["https://..."],
            "repositories":     ["GEO", "GitHub"],
            "accession_codes":  {"GEO_series": ["GSE123456"], ...},
        }
    """
    # Extract all URLs
    url_pattern = r"https?://[^\s\)\]\}\'\"\<\>]+"
    urls = list(set(re.findall(url_pattern, text)))

    # Identify repositories from URLs
    repositories = []
    for url in urls:
        for substr, label in REPO_URL_MAP.items():
            if substr in url.lower() and label not in repositories:
                repositories.append(label)

    # Also catch text-only mentions
    for label, pattern in REPO_TEXT_MAP.items():
        if re.search(pattern, text, re.IGNORECASE) and label not in repositories:
            repositories.append(label)

    accession_codes = extract_accession_codes(text)

    return {
        "urls":            urls,
        "repositories":    repositories,
        "accession_codes": accession_codes,
    }


def flatten_accessions(accession_dict: dict) -> dict:
    """
    Flatten accession dict into spreadsheet-ready columns.
    e.g. {"accession_GEO_series": "GSE123456", "accession_BioProject_NCBI": "PRJNA805052"}
    """
    return {
        f"accession_{db}": "; ".join(codes)
        for db, codes in accession_dict.items()
    }
