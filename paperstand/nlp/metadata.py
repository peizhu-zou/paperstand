"""
nlp/metadata.py
Regex-based extraction of study metadata from paper text.

Extracts:
  - Sample sizes (total, diseased, healthy)
  - Age groups
  - Species / organism
  - Study design keywords
  - Sequencing technologies
  - Disease terms (regex fallback — entities.py handles deep NER)

This module is fast (no model loading) and works on any machine.
It is the first pass before running PubMedBERT NER.
"""

import re


# ── Pattern tables ────────────────────────────────────────────────────────────

AGE_PATTERNS = [
    # "18-65 years", "18 to 65 years old"
    r"\b(\d{1,3})\s*[-–to]+\s*(\d{1,3})\s*(?:years?(?:\s*old)?|yr|yo)\b",
    # "mean age of 45.2", "median age 32"
    r"\b(?:mean|median|average)\s+age\s+(?:of\s+)?(\d{1,3}(?:\.\d+)?)\b",
    # "aged 25-40"
    r"\baged?\s+(\d{1,3})\s*[-–to]+\s*(\d{1,3})\b",
    # "≥18 years", ">65 years"
    r"[≥><=]+\s*(\d{1,3})\s*(?:years?|yr)\b",
    # categorical: "children", "adults", "elderly", etc.
    r"\b(neonates?|infants?|children|adolescents?|adults?|elderly|"
    r"older adults?|pediatric|geriatric|neonatal)\b",
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
    r"\b(Sus scrofa|porcine|pig model)\b",
    r"\b(Gallus gallus|chicken|poultry)\b",
]

# Total sample size
SAMPLE_SIZE_PATTERNS = [
    r"\bn\s*=\s*(\d+)\b",
    r"\b(\d+)\s+(?:patients?|subjects?|participants?|individuals?|"
    r"samples?|cases?|controls?|cohort members?|volunteers?|donors?)\b",
    r"\ba total of\s+(\d+)\b",
    r"\b(\d+)\s+(?:healthy|diseased|affected|unaffected)\s+"
    r"(?:patients?|subjects?|individuals?|samples?)\b",
]

# Diseased / case samples
DISEASED_PATTERNS = [
    r"\b(\d+)\s+(?:patients?|cases?|affected|diseased|diagnosed)\b",
    r"\b(\d+)\s+(?:\w+\s+)?(?:patients?|cases?)\s+with\b",
    r"\b(\d+)\s+(?:\w+\s+)?(?:affected|diseased)\s+(?:individuals?|samples?)\b",
]

# Healthy / control samples
HEALTHY_PATTERNS = [
    r"\b(\d+)\s+(?:controls?|healthy|normal|unaffected)\b",
    r"\b(\d+)\s+healthy\s+(?:subjects?|individuals?|volunteers?|donors?|controls?)\b",
    r"\b(\d+)\s+age-?matched\s+controls?\b",
]

STUDY_DESIGN_KEYWORDS = [
    "randomized controlled trial", "RCT",
    "cohort study", "case-control", "case control",
    "cross-sectional", "longitudinal",
    "prospective", "retrospective",
    "meta-analysis", "systematic review",
    "single-cell", "single cell",
    "bulk RNA-seq", "bulk RNAseq",
    "GWAS", "genome-wide association",
    "whole exome sequencing", "whole genome sequencing",
    "RNA sequencing", "RNA-seq", "RNAseq",
    "scRNA-seq", "scRNAseq",
    "ChIP-seq", "ChIPseq",
    "ATAC-seq", "ATACseq",
    "proteomics", "metabolomics", "epigenomics",
    "metagenomics", "transcriptomics", "lipidomics",
    "multi-omics", "multiomics",
]

SEQ_TECH_KEYWORDS = [
    # Illumina platforms
    "Illumina", "NovaSeq", "HiSeq", "MiSeq", "NextSeq", "iSeq",
    # 10x Genomics
    "10x Genomics", "10X Chromium", "Chromium",
    # Long-read
    "Oxford Nanopore", "Nanopore", "PacBio", "SMRT",
    # Classic
    "Sanger sequencing",
    # Assay types
    "bulk RNA-seq", "scRNA-seq", "single-cell RNA",
    "whole genome sequencing", "WGS",
    "whole exome sequencing", "WES",
    "ChIP-seq", "ATAC-seq", "Hi-C", "Cut&Run", "CUT&RUN",
    "snRNA-seq", "snATAC-seq", "spatial transcriptomics",
    "Visium", "MERFISH", "seqFISH",
    "CITE-seq", "CITEseq",
]

DISEASE_PATTERNS = [
    r"\b(?:cancer|carcinoma|tumor|tumour|neoplasm|malignancy|"
    r"lymphoma|leukemia|leukaemia|melanoma|sarcoma|glioma|glioblastoma)\b",
    r"\b(?:diabetes|diabetic|type [12] diabetes|T[12]D|T2DM|T1DM)\b",
    r"\b(?:Alzheimer|Parkinson|Huntington|ALS|amyotrophic lateral sclerosis|"
    r"multiple sclerosis|MS)\b",
    r"\b(?:COVID-19|SARS-CoV-2|coronavirus|influenza|HIV|AIDS|hepatitis|"
    r"tuberculosis|TB|malaria)\b",
    r"\b(?:hypertension|heart disease|cardiovascular|atherosclerosis|"
    r"stroke|myocardial infarction|heart failure)\b",
    r"\b(?:depression|anxiety|schizophrenia|bipolar|PTSD|"
    r"autism|ASD|ADHD|OCD)\b",
    r"\b(?:obesity|metabolic syndrome|NAFLD|NASH|fatty liver)\b",
    r"\b(?:asthma|COPD|pulmonary fibrosis|lung disease|emphysema)\b",
    r"\b(?:IBD|Crohn|ulcerative colitis|celiac|coeliac|IBS)\b",
    r"\b(?:lupus|SLE|rheumatoid arthritis|autoimmune|psoriasis)\b",
    r"\b(?:sepsis|pneumonia|meningitis|encephalitis)\b",
    r"\b(?:epilepsy|seizure|neuropathy|dementia|neurodegeneration)\b",
]


# ── Public functions ──────────────────────────────────────────────────────────

def extract_age_info(text: str) -> list:
    """Extract age ranges and categories from text."""
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
    """Extract total sample size numbers."""
    found = []
    for pattern in SAMPLE_SIZE_PATTERNS:
        matches = re.findall(pattern, text, re.IGNORECASE)
        for m in matches:
            found.append(m if isinstance(m, str) else str(m))
    return list(set(found))


def extract_diseased_healthy_counts(text: str) -> dict:
    """
    Extract diseased vs healthy/control sample counts.

    Returns:
        {"diseased": ["120", "45"], "healthy": ["100"]}
    """
    diseased = []
    for pattern in DISEASED_PATTERNS:
        diseased.extend(re.findall(pattern, text, re.IGNORECASE))

    healthy = []
    for pattern in HEALTHY_PATTERNS:
        healthy.extend(re.findall(pattern, text, re.IGNORECASE))

    return {
        "diseased": list(set(diseased)),
        "healthy":  list(set(healthy)),
    }


def extract_study_design(text: str) -> list:
    """Identify study design type keywords present in text."""
    return [
        kw for kw in STUDY_DESIGN_KEYWORDS
        if re.search(re.escape(kw), text, re.IGNORECASE)
    ]


def extract_sequencing_tech(text: str) -> list:
    """Identify sequencing/assay technology keywords."""
    return [
        kw for kw in SEQ_TECH_KEYWORDS
        if re.search(re.escape(kw), text, re.IGNORECASE)
    ]


def extract_diseases_regex(text: str) -> list:
    """
    Extract disease/condition mentions using regex.
    Fast but not exhaustive — use entities.py for deep NER.
    """
    found = []
    for pattern in DISEASE_PATTERNS:
        found.extend(re.findall(pattern, text, re.IGNORECASE))
    return list(set(m.lower() for m in found))


def extract_all_metadata(text: str) -> dict:
    """
    Run all regex extractors on a text string.
    Returns a flat dict ready to merge into a record.

    Args:
        text: combined section text (usually abstract + methods + results)

    Returns:
        dict with keys: age_groups, species, sample_sizes,
                        diseased_counts, healthy_counts,
                        study_design, seq_technologies, diseases
    """
    counts = extract_diseased_healthy_counts(text)
    return {
        "age_groups":      extract_age_info(text),
        "species":         extract_species(text),
        "sample_sizes":    extract_sample_sizes(text),
        "diseased_counts": counts["diseased"],
        "healthy_counts":  counts["healthy"],
        "study_design":    extract_study_design(text),
        "seq_technologies": extract_sequencing_tech(text),
        "diseases":        extract_diseases_regex(text),
    }


def clean_for_bert(text: str) -> str:
    """
    Clean text for input to PubMedBERT.
    Removes citation brackets, figure refs, excess whitespace.
    """
    text = re.sub(r"\[\d+(?:,\s*\d+)*\]", "", text)    # [1], [2,3]
    text = re.sub(r"\(\s*Fig\.?\s*\d+\w*\)", "", text)  # (Fig. 1a)
    text = re.sub(r"\(\s*Table\s*\d+\w*\)", "", text)   # (Table 2)
    text = re.sub(r"\(\s*Supplementary.*?\)", "", text)  # (Supplementary Fig. S1)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def chunk_text(text: str, max_chars: int = 1500) -> list:
    """
    Split text into chunks ≤ max_chars, breaking at sentence boundaries.
    PubMedBERT has a 512-token (~1500 char) context limit.
    """
    if len(text) <= max_chars:
        return [text]

    chunks = []
    sentences = re.split(r"(?<=[.!?])\s+", text)
    current = ""
    for sentence in sentences:
        if len(current) + len(sentence) > max_chars:
            if current:
                chunks.append(current.strip())
            current = sentence
        else:
            current += " " + sentence
    if current:
        chunks.append(current.strip())
    return chunks
