"""
export.py
Export extracted paper records to CSV or Excel spreadsheet.
"""

import pandas as pd
import os
from pathlib import Path


# Columns to include and their display order in the spreadsheet
COLUMN_ORDER = [
    "pmcid",
    "doi",
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


def records_to_dataframe(records: list) -> pd.DataFrame:
    """
    Convert a list of extracted record dicts to a pandas DataFrame.

    Args:
        records: list of flat dicts from extract.extract_fields()

    Returns:
        DataFrame with standardized columns
    """
    df = pd.DataFrame(records)

    # Reorder columns: known columns first, then any extras
    existing_cols = [c for c in COLUMN_ORDER if c in df.columns]
    extra_cols = [c for c in df.columns if c not in COLUMN_ORDER]
    df = df[existing_cols + extra_cols]

    return df


def export_to_csv(records: list, output_path: str = "output/papers.csv") -> str:
    """
    Export records to a CSV file.

    Args:
        records: list of flat record dicts
        output_path: file path for the CSV

    Returns:
        Path to saved CSV
    """
    Path(os.path.dirname(output_path)).mkdir(parents=True, exist_ok=True)
    df = records_to_dataframe(records)
    df.to_csv(output_path, index=False, encoding="utf-8-sig")
    print(f"[export] Saved CSV → {output_path} ({len(df)} rows)")
    return output_path


def export_to_excel(records: list, output_path: str = "output/papers.xlsx") -> str:
    """
    Export records to an Excel file with basic formatting.

    Args:
        records: list of flat record dicts
        output_path: file path for the Excel file

    Returns:
        Path to saved Excel file
    """
    Path(os.path.dirname(output_path)).mkdir(parents=True, exist_ok=True)
    df = records_to_dataframe(records)

    with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Papers")

        # Auto-size columns
        worksheet = writer.sheets["Papers"]
        for col_idx, col in enumerate(df.columns, 1):
            max_len = max(
                len(str(col)),
                df[col].astype(str).str.len().max() if not df[col].empty else 0
            )
            # Cap column width to 60 chars for readability
            worksheet.column_dimensions[
                worksheet.cell(row=1, column=col_idx).column_letter
            ].width = min(max_len + 2, 60)

    print(f"[export] Saved Excel → {output_path} ({len(df)} rows)")
    return output_path


def export(records: list, output_path: str = "output/papers.csv") -> str:
    """
    Auto-detect format from output_path extension and export.

    Args:
        records: list of flat record dicts
        output_path: file path (.csv or .xlsx)

    Returns:
        Path to saved file
    """
    ext = os.path.splitext(output_path)[-1].lower()
    if ext == ".xlsx":
        return export_to_excel(records, output_path)
    else:
        return export_to_csv(records, output_path)
