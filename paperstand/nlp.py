"""
nlp.py
Stretch goal: extract supplementary metadata from paper text using NLP.
Identifies: age groups, diseases/conditions, species, accession codes.

Uses regex-based extraction (no external model required) plus optional
spaCy/scispaCy integration for named entity recognition.
"""

import re
from paperstand.extract import extract_accession_codes


# ── Regex-based extractors ───────────────────────────────────────────────────

AGE_PATTERNS = [
    # "18-65 years", "18 to 65 years old"
    r"\b(\d{1,3})\s*[-–to]+\s*(\d{1,3})\s*(?:years?(?:\s*old)?|yr|yo)\b",
    # "mean age of 45", "median age 32"
    r"\b(?:mean|median|average)\s+age\s+(?:of\s+)?(\d{1,3}(?:\.\d+)?)\b",
    # "aged 25-40"
    r"\baged?\s+(\d{1,3})\s*[-–to]+\s*(\d{1,3})\b",
    # "≥18 years", ">65 years"
    r"[≥><=]+\s*(\d{1,3})\s*(?:years?|yr)\b",
    # "children", "adults", "elderly"
    r"\b(neonates?|infants?|children|adolescents?|adults?|elderly|older adults?|pediatric|geriatric)\b",
]

SPECIES_PATTERNS = [
    r"\b(Mus musculus|mice|mouse|murine)\b",
    r"\b(Rattus norvegicus|rats?|rat model)\b",
    r"\b(Homo sapiens|humans?|human subjects?|patients?|participants?)\b",
    r"\b(Drosophila melanogaster|fruit fl(?:y|ies))\b",
    r"\b(Caenorhabditis elegans|C\. elegans)\b",
    r"\b(Danio rerio|zebrafish)\b",
    r"\b(Arabidopsis thaliana)\b",
    r"\b(Saccharomyces cerevisiae|yeast)\b",
    r"\b(Escherichia coli|E\. coli)\b",
    r"\b(Macaca mulatta|rhesus macaque|non-human primate|NHP)\b",
]

SAMPLE_SIZE_PATTERNS = [
    # "n = 120", "N=45"
    r"\bn\s*=\s*(\d+)\b",
    # "120 patients", "45 subjects", "200 participants"
    r"\b(\d+)\s+(?:patients?|subjects?|participants?|individuals?|samples?|cases?|controls?|cohort members?)\b",
    # "a total of 300"
    r"\ba total of\s+(\d+)\b",
]

STUDY_DESIGN_KEYWORDS = [
    "randomized controlled trial", "RCT", "cohort study", "case-control",
    "cross-sectional", "longitudinal", "prospective", "retrospective",
    "meta-analysis", "systematic review", "single-cell", "bulk RNA-seq",
    "GWAS", "genome-wide association", "whole exome", "whole genome",
    "RNA sequencing", "RNA-seq", "scRNA-seq", "ChIP-seq", "ATAC-seq",
    "proteomics", "metabolomics", "epigenomics",
]

SEQ_TECH_KEYWORDS = [
    "Illumina", "NovaSeq", "HiSeq", "MiSeq",
    "10x Genomics", "10X Chromium",
    "Oxford Nanopore", "PacBio", "SMRT",
    "Sanger sequencing",
    "bulk RNA-seq", "scRNA-seq", "single-cell RNA",
    "whole genome sequencing", "WGS",
    "whole exome sequencing", "WES",
    "ChIP-seq", "ATAC-seq", "Hi-C", "Cut&Run",
]


def extract_age_info(text: str) -> list:
    """Extract age-related information from text."""
    found = []
    for pattern in AGE_PATTERNS:
        matches = re.findall(pattern, text, re.IGNORECASE)
        for match in matches:
            if isinstance(match, tuple):
                found.append("-".join(str(m) for m in match if m))
            else:
                found.append(str(match))
    return list(set(found))


def extract_species(text: str) -> list:
    """Extract organism/species mentions."""
    found = []
    for pattern in SPECIES_PATTERNS:
        matches = re.findall(pattern, text, re.IGNORECASE)
        found.extend([m if isinstance(m, str) else m[0] for m in matches])
    return list(set(found))


def extract_sample_sizes(text: str) -> list:
    """Extract reported sample sizes."""
    found = []
    for pattern in SAMPLE_SIZE_PATTERNS:
        matches = re.findall(pattern, text, re.IGNORECASE)
        found.extend(matches)
    return list(set(found))


def extract_study_design(text: str) -> list:
    """Identify study design keywords present in the text."""
    found = []
    for keyword in STUDY_DESIGN_KEYWORDS:
        if re.search(re.escape(keyword), text, re.IGNORECASE):
            found.append(keyword)
    return found


def extract_sequencing_tech(text: str) -> list:
    """Identify sequencing technology keywords."""
    found = []
    for keyword in SEQ_TECH_KEYWORDS:
        if re.search(re.escape(keyword), text, re.IGNORECASE):
            found.append(keyword)
    return found


def extract_diseases(text: str) -> list:
    """
    Extract disease/condition mentions using regex patterns.
    For more comprehensive extraction, use scispaCy NER (see enrich_with_spacy).
    """
    patterns = [
        r"\b(?:cancer|carcinoma|tumor|tumour|neoplasm|malignancy|lymphoma|leukemia|melanoma)\b",
        r"\b(?:diabetes|diabetic|type [12] diabetes|T[12]D)\b",
        r"\b(?:Alzheimer|Parkinson|Huntington|ALS|multiple sclerosis|MS)\b",
        r"\b(?:COVID-19|SARS-CoV-2|coronavirus|influenza|HIV|AIDS|hepatitis)\b",
        r"\b(?:hypertension|heart disease|cardiovascular|atherosclerosis|stroke)\b",
        r"\b(?:depression|anxiety|schizophrenia|bipolar|PTSD|autism|ASD|ADHD)\b",
        r"\b(?:obesity|metabolic syndrome|NAFLD|NASH)\b",
        r"\b(?:asthma|COPD|pulmonary fibrosis|lung disease)\b",
        r"\b(?:IBD|Crohn|ulcerative colitis|celiac|IBS)\b",
        r"\b(?:lupus|SLE|rheumatoid arthritis|autoimmune)\b",
    ]

    found = []
    for pattern in patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        found.extend(matches)

    return list(set(m.lower() for m in found))


def enrich_record_with_nlp(record: dict) -> dict:
    """
    Add NLP-derived metadata fields to an extracted record.
    Searches across abstract + methods + results text.

    Args:
        record: flat record dict from extract.extract_fields()

    Returns:
        Same dict with added nlp_* fields
    """
    # Combine relevant sections for NLP
    search_text = " ".join([
        record.get("abstract", ""),
        record.get("methods", ""),
        record.get("results", ""),
        record.get("data_availability", ""),
    ])

    record["nlp_age_groups"] = "; ".join(extract_age_info(search_text))
    record["nlp_species"] = "; ".join(extract_species(search_text))
    record["nlp_sample_sizes"] = "; ".join(extract_sample_sizes(search_text))
    record["nlp_study_design"] = "; ".join(extract_study_design(search_text))
    record["nlp_seq_technologies"] = "; ".join(extract_sequencing_tech(search_text))
    record["nlp_diseases"] = "; ".join(extract_diseases(search_text))

    # Accession codes from data availability + methods
    accession_text = record.get("data_availability", "") + " " + record.get("methods", "")
    accessions = extract_accession_codes(accession_text)
    for code_type, codes in accessions.items():
        record[f"accession_{code_type}"] = "; ".join(codes)

    return record


def enrich_records_with_nlp(records: list) -> list:
    """Run NLP enrichment on a list of records."""
    enriched = []
    for record in records:
        print(f"[nlp] Enriching {record.get('pmcid', '?')}...")
        enriched.append(enrich_record_with_nlp(record))
    return enriched


# ── Optional: scispaCy NER ───────────────────────────────────────────────────

def enrich_with_spacy(record: dict, nlp_model=None) -> dict:
    """
    Optional: use scispaCy for biomedical named entity recognition.
    Requires: pip install scispacy
              pip install https://s3-us-west-2.amazonaws.com/ai2-s2-scispacy/releases/v0.5.3/en_core_sci_sm-0.5.3.tar.gz

    Args:
        record: flat record dict
        nlp_model: loaded spaCy model (pass in to avoid reloading)

    Returns:
        Record with added spacy_entities field
    """
    try:
        import spacy
    except ImportError:
        print("[nlp] spaCy not installed. Run: pip install scispacy")
        return record

    if nlp_model is None:
        try:
            nlp_model = spacy.load("en_core_sci_sm")
        except OSError:
            print("[nlp] scispaCy model not found. See docstring for install instructions.")
            return record

    text = record.get("abstract", "") + " " + record.get("methods", "")
    doc = nlp_model(text[:100000])  # cap length

    entities = {}
    for ent in doc.ents:
        label = ent.label_
        entities.setdefault(label, []).append(ent.text)

    for label, vals in entities.items():
        record[f"spacy_{label.lower()}"] = "; ".join(set(vals))

    return record
