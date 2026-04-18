"""
nlp/__init__.py
Public API for the PaperStand NLP module.

Three submodules:
  accession  — regex extraction of repository URLs and accession codes
               (GEO, SRA, BioProject, dbGaP, Zenodo, etc.)
  metadata   — regex extraction of cohort metadata
               (sample sizes, age, species, study design, sequencing tech, diseases)
  entities   — deep NER using PubMedBERT or scispaCy
               (disease names, handoff format for Group 2 ML pipeline)

Typical usage:

  # Fast regex pass — no model needed
  from paperstand.nlp import enrich_record, enrich_records
  records = enrich_records(records)

  # Export clean JSON for Group 2's PubMedBERT pipeline
  from paperstand.nlp import export_bert_inputs
  export_bert_inputs(records, "output/bert_inputs.json")

  # Run PubMedBERT inference directly (requires: pip install transformers torch)
  from paperstand.nlp import run_pubmedbert
  results = run_pubmedbert(records, "output/bert_results.json")
"""

from .accession import (
    extract_accession_codes,
    extract_data_availability,
    flatten_accessions,
)

from .metadata import (
    extract_age_info,
    extract_species,
    extract_sample_sizes,
    extract_diseased_healthy_counts,
    extract_study_design,
    extract_sequencing_tech,
    extract_diseases_regex,
    extract_all_metadata,
    clean_for_bert,
    chunk_text,
)

from .entities import (
    prepare_bert_inputs,
    export_bert_inputs,
    run_pubmedbert,
    run_scispacy,
)


# ── Convenience functions ─────────────────────────────────────────────────────

def enrich_record(record: dict) -> dict:
    """
    Run all regex NLP extractors on a single record.
    Adds nlp_* and accession_* fields. No model required.

    Searches across: abstract + methods + results + data_availability

    Args:
        record: flat dict from extractor

    Returns:
        Same dict with added nlp_* and accession_* fields
    """
    # Combine relevant sections
    search_text = " ".join([
        record.get("abstract", ""),
        record.get("methods", ""),
        record.get("results", ""),
        record.get("data_availability", ""),
    ])

    # Metadata extraction
    meta = extract_all_metadata(search_text)
    record["nlp_age_groups"]       = "; ".join(meta["age_groups"])
    record["nlp_species"]          = "; ".join(meta["species"])
    record["nlp_sample_sizes"]     = "; ".join(meta["sample_sizes"])
    record["nlp_diseased_counts"]  = "; ".join(meta["diseased_counts"])
    record["nlp_healthy_counts"]   = "; ".join(meta["healthy_counts"])
    record["nlp_study_design"]     = "; ".join(meta["study_design"])
    record["nlp_seq_technologies"] = "; ".join(meta["seq_technologies"])
    record["nlp_diseases"]         = "; ".join(meta["diseases"])

    # Accession codes — search data availability + methods
    accession_text = (
        record.get("data_availability", "") + " " +
        record.get("methods", "")
    )
    da = extract_data_availability(accession_text)
    record["data_availability_urls"]         = "; ".join(da["urls"])
    record["data_availability_repositories"] = "; ".join(da["repositories"])
    record.update(flatten_accessions(da["accession_codes"]))

    return record


def enrich_records(records: list) -> list:
    """Run enrich_record() on a list of records."""
    enriched = []
    for record in records:
        identifier = record.get("identifier", record.get("pmcid", "?"))
        print(f"[nlp] Enriching {identifier}...")
        enriched.append(enrich_record(record))
    return enriched


__all__ = [
    # accession
    "extract_accession_codes",
    "extract_data_availability",
    "flatten_accessions",
    # metadata
    "extract_age_info",
    "extract_species",
    "extract_sample_sizes",
    "extract_diseased_healthy_counts",
    "extract_study_design",
    "extract_sequencing_tech",
    "extract_diseases_regex",
    "extract_all_metadata",
    "clean_for_bert",
    "chunk_text",
    # entities
    "prepare_bert_inputs",
    "export_bert_inputs",
    "run_pubmedbert",
    "run_scispacy",
    # convenience
    "enrich_record",
    "enrich_records",
]
