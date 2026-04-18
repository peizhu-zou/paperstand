"""
exporter.py
Export extracted records to CSV, Excel, or JSON.

  .csv   → spreadsheet, good for manual review and Excel/Sheets
  .xlsx  → Excel with auto-sized columns
  .json  → structured output; use bert_ready=True for Group 2's ML pipeline
"""

import pandas as pd
import json
import os
from pathlib import Path


# Columns shown first in spreadsheet, in this order.
# NLP and accession columns (nlp_*, accession_*) are appended after.
COLUMN_ORDER = [
    "identifier",
    "doi",
    "url",
    "title",
    "authors",
    "journal",
    "date",
    "keywords",
    "abstract",
    "introduction",
    "methods",
    "results",
    "discussion",
    "conclusion",
    "data_availability",
    "data_availability_urls",
    "data_availability_repositories",
    "funding",
    "acknowledgements",
    "ethics",
    "conflict_of_interest",
    "author_contributions",
    "n_figures",
    "n_tables",
    "n_references",
    "section_headings_found",
]


# ── Public functions ──────────────────────────────────────────────────────────

def to_csv(records: list, output_path: str = "output/papers.csv") -> str:
    """
    Export records to a CSV file.

    Args:
        records:     list of flat record dicts from extractor
        output_path: output file path

    Returns:
        Path to saved file
    """
    _ensure_dir(output_path)
    df = _to_dataframe(records)
    df.to_csv(output_path, index=False, encoding="utf-8-sig")
    print(f"[exporter] Saved CSV  → {output_path} ({len(df)} rows)")
    return output_path


def to_excel(records: list, output_path: str = "output/papers.xlsx") -> str:
    """
    Export records to an Excel file with auto-sized columns.

    Args:
        records:     list of flat record dicts
        output_path: output file path

    Returns:
        Path to saved file
    """
    _ensure_dir(output_path)
    df = _to_dataframe(records)

    with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Papers")

        ws = writer.sheets["Papers"]
        for col_idx, col in enumerate(df.columns, 1):
            max_len = max(
                len(str(col)),
                df[col].astype(str).str.len().max() if not df[col].empty else 0,
            )
            ws.column_dimensions[
                ws.cell(row=1, column=col_idx).column_letter
            ].width = min(max_len + 2, 60)

    print(f"[exporter] Saved Excel → {output_path} ({len(df)} rows)")
    return output_path


def to_json(records: list,
            output_path: str = "output/papers.json",
            bert_ready: bool = False) -> str:
    """
    Export records to a JSON file.

    Args:
        records:     list of flat record dicts
        output_path: output file path
        bert_ready:  if True, embed a 'bert_input' block in each record
                     with cleaned accession_text / sample_text / disease_text
                     — this is the handoff format for Group 2's ML pipeline

    Returns:
        Path to saved file
    """
    _ensure_dir(output_path)

    output = []
    for record in records:
        entry = dict(record)
        if bert_ready:
            from paperstand.nlp.entities import _prepare_single_bert_input
            entry["bert_input"] = _prepare_single_bert_input(record)
        output.append(entry)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    print(f"[exporter] Saved JSON  → {output_path} ({len(output)} records)")
    return output_path


def save(records: list,
         output_path: str = "output/papers.csv",
         bert_ready: bool = False) -> str:
    """
    Auto-detect format from file extension and export.

    Args:
        records:     list of flat record dicts
        output_path: file path — extension determines format
                     .csv  → CSV
                     .xlsx → Excel
                     .json → JSON
        bert_ready:  passed through to to_json() only

    Returns:
        Path to saved file
    """
    ext = os.path.splitext(output_path)[-1].lower()
    if ext == ".xlsx":
        return to_excel(records, output_path)
    elif ext == ".json":
        return to_json(records, output_path, bert_ready=bert_ready)
    else:
        return to_csv(records, output_path)


# ── Private helpers ───────────────────────────────────────────────────────────

def _to_dataframe(records: list) -> pd.DataFrame:
    """Convert records to DataFrame with standardized column ordering."""
    df = pd.DataFrame(records)
    known   = [c for c in COLUMN_ORDER if c in df.columns]
    extra   = [c for c in df.columns   if c not in COLUMN_ORDER]
    return df[known + extra]


def _ensure_dir(output_path: str) -> None:
    """Create output directory if it doesn't exist."""
    dirname = os.path.dirname(output_path)
    if dirname:
        Path(dirname).mkdir(parents=True, exist_ok=True)
