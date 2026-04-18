"""
nlp/entities.py
Deep named entity recognition using pre-trained biomedical models.

Two backends (use either or both):

  1. PubMedBERT — transformer NER for disease entities
     Model: https://huggingface.co/pruas/BENT-PubMedBERT-NER-Disease
     Install: pip install transformers torch
     Best for: disease name extraction from abstract/methods/results

  2. scispaCy — biomedical NLP pipeline
     Install: pip install scispacy
              pip install https://s3-us-west-2.amazonaws.com/ai2-s2-scispacy/
                          releases/v0.5.3/en_core_sci_sm-0.5.3.tar.gz
     Best for: broad biomedical entity extraction (chemicals, genes, species)

Group 2 handoff:
  - prepare_bert_inputs()  → clean JSON for Group 2 to run their own model
  - run_pubmedbert()       → run inference here if transformers is installed
"""

import json
import os
from pathlib import Path

from .accession import extract_accession_codes
from .metadata  import (
    extract_diseases_regex,
    extract_diseased_healthy_counts,
    extract_sample_sizes,
    clean_for_bert,
    chunk_text,
)

PUBMEDBERT_MODEL = "pruas/BENT-PubMedBERT-NER-Disease"


# ── PubMedBERT ────────────────────────────────────────────────────────────────

def prepare_bert_inputs(records: list) -> list:
    """
    Build clean, section-labeled input dicts for PubMedBERT NER.
    This is the handoff format for Group 2's ML pipeline.

    Each output record has three text fields targeting specific NER tasks:
      accession_text → for accession code extraction (data availability + methods)
      sample_text    → for cohort size extraction   (methods + results + abstract)
      disease_text   → for disease NER              (abstract + methods + results)

    Args:
        records: list of flat record dicts from extractor

    Returns:
        list of bert input dicts
    """
    return [_prepare_single_bert_input(r) for r in records]


def _prepare_single_bert_input(record: dict) -> dict:
    """Prepare one record for BERT input."""
    return {
        "identifier":     record.get("identifier", record.get("pmcid", "")),
        "doi":            record.get("doi", ""),
        "title":          record.get("title", ""),
        "accession_text": clean_for_bert(
            record.get("data_availability", "") + " " +
            record.get("methods", "")
        ),
        "sample_text":    clean_for_bert(
            record.get("methods", "") + " " +
            record.get("results", "") + " " +
            record.get("abstract", "")
        ),
        "disease_text":   clean_for_bert(
            record.get("abstract", "") + " " +
            record.get("methods", "") + " " +
            record.get("results", "")
        ),
    }


def export_bert_inputs(records: list,
                       output_path: str = "output/bert_inputs.json") -> str:
    """
    Save PubMedBERT-ready inputs as JSON for Group 2.

    Args:
        records:     list of flat record dicts
        output_path: where to save

    Returns:
        Path to saved JSON file
    """
    Path(os.path.dirname(output_path)).mkdir(parents=True, exist_ok=True)

    bert_inputs = prepare_bert_inputs(records)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(bert_inputs, f, indent=2, ensure_ascii=False)

    print(f"[entities] Saved BERT inputs → {output_path} ({len(bert_inputs)} records)")
    return output_path


def run_pubmedbert(records: list,
                   output_path: str = "output/bert_results.json",
                   score_threshold: float = 0.7) -> list:
    """
    Run PubMedBERT NER on a batch of records.
    Loads the model once and reuses across all papers.

    Requires: pip install transformers torch

    Args:
        records:         list of flat record dicts
        output_path:     where to save JSON results
        score_threshold: minimum confidence score to include an entity (0-1)

    Returns:
        List of dicts with added bert_* fields:
          bert_diseases        — disease entities from disease_text
          bert_accessions      — accession codes from accession_text
          bert_sample_sizes    — total sample counts from sample_text
          bert_diseased_counts — diseased/case counts
          bert_healthy_counts  — healthy/control counts
    """
    try:
        from transformers import (
            pipeline,
            AutoTokenizer,
            AutoModelForTokenClassification,
        )
    except ImportError:
        print("[entities] transformers not installed. Run: pip install transformers torch")
        return records

    print(f"[entities] Loading {PUBMEDBERT_MODEL}...")
    tokenizer = AutoTokenizer.from_pretrained(PUBMEDBERT_MODEL)
    model     = AutoModelForTokenClassification.from_pretrained(PUBMEDBERT_MODEL)
    ner       = pipeline(
        "ner",
        model=model,
        tokenizer=tokenizer,
        aggregation_strategy="simple",  # merge subword tokens → whole words
    )

    results = []
    for record in records:
        identifier = record.get("identifier", record.get("pmcid", "?"))
        print(f"[entities] Running BERT NER on {identifier}...")
        bert_input = _prepare_single_bert_input(record)
        enriched   = _run_ner_on_input(bert_input, ner, score_threshold)
        results.append({**record, **enriched})

    # Save results
    Path(os.path.dirname(output_path)).mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print(f"[entities] Saved BERT results → {output_path}")

    return results


def _run_ner_on_input(bert_input: dict, ner_pipeline,
                      score_threshold: float = 0.7) -> dict:
    """
    Run NER pipeline on one prepared input dict.
    Returns a dict of bert_* fields to merge into the record.
    """
    result = {}

    # ── Disease NER from disease_text ─────────────────────────────────────────
    disease_text = bert_input.get("disease_text", "")
    if disease_text:
        diseases = []
        for chunk in chunk_text(disease_text):
            try:
                entities = ner_pipeline(chunk)
                diseases.extend(
                    ent["word"] for ent in entities
                    if ent.get("score", 0) >= score_threshold
                )
            except Exception as e:
                print(f"[entities] BERT error: {e}")
        result["bert_diseases"] = "; ".join(sorted(set(diseases)))
    else:
        result["bert_diseases"] = ""

    # ── Accession codes — regex is more reliable than BERT for this ───────────
    accession_text = bert_input.get("accession_text", "")
    accessions = extract_accession_codes(accession_text)
    all_codes  = [code for codes in accessions.values() for code in codes]
    result["bert_accessions"] = "; ".join(sorted(set(all_codes)))

    # ── Sample counts — regex on sample_text ──────────────────────────────────
    sample_text = bert_input.get("sample_text", "")
    counts      = extract_diseased_healthy_counts(sample_text)
    result["bert_diseased_counts"] = "; ".join(counts["diseased"])
    result["bert_healthy_counts"]  = "; ".join(counts["healthy"])
    result["bert_sample_sizes"]    = "; ".join(extract_sample_sizes(sample_text))

    return result


# ── scispaCy ──────────────────────────────────────────────────────────────────

def run_scispacy(records: list, nlp_model=None) -> list:
    """
    Run scispaCy NER on a list of records.
    Adds spacy_* fields for each entity type found.

    Requires:
      pip install scispacy
      pip install https://s3-us-west-2.amazonaws.com/ai2-s2-scispacy/
                  releases/v0.5.3/en_core_sci_sm-0.5.3.tar.gz

    Args:
        records:   list of flat record dicts
        nlp_model: pre-loaded spaCy model (pass to avoid reloading)

    Returns:
        List of records with added spacy_* fields
    """
    try:
        import spacy
    except ImportError:
        print("[entities] spaCy not installed. Run: pip install scispacy")
        return records

    if nlp_model is None:
        try:
            nlp_model = spacy.load("en_core_sci_sm")
        except OSError:
            print("[entities] scispaCy model not found. See docstring for install instructions.")
            return records

    enriched = []
    for record in records:
        identifier = record.get("identifier", record.get("pmcid", "?"))
        print(f"[entities] Running scispaCy on {identifier}...")

        # Combine abstract + methods for NER
        text = " ".join([
            record.get("abstract", ""),
            record.get("methods", ""),
        ])
        doc = nlp_model(text[:100_000])  # cap to avoid memory issues

        entity_map = {}
        for ent in doc.ents:
            entity_map.setdefault(ent.label_, []).append(ent.text)

        new_record = dict(record)
        for label, vals in entity_map.items():
            new_record[f"spacy_{label.lower()}"] = "; ".join(sorted(set(vals)))

        enriched.append(new_record)

    return enriched
