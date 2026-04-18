"""
cli.py
Command-line interface for PaperStand.

Usage examples:
    # Single paper
    python cli.py --pmcid PMC7012345 --output output/results.csv

    # Multiple papers
    python cli.py --pmcids PMC7012345 PMC6543210 PMC9876543 --output output/results.xlsx

    # From a text file (one PMCID per line)
    python cli.py --pmcid-file pmcids.txt --output output/results.xlsx

    # Enable NLP enrichment
    python cli.py --pmcid PMC7012345 --output output/results.csv --nlp

    # Load from cached HTML files (skip downloading)
    python cli.py --html-dir data/sample_papers --output output/results.csv
"""

import argparse
import sys
import os

# Allow running cli.py from repo root
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "paperstand"))

from paperstand.fetch import fetch_multiple, load_html_from_file
from paperstand.parse import parse_multiple
from paperstand.extract import extract_fields_multiple
from paperstand.export import export
from paperstand.nlp import enrich_records_with_nlp


def parse_args():
    parser = argparse.ArgumentParser(
        prog="paperstand",
        description="Extract structured data from PubMed Central papers into a spreadsheet.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python cli.py --pmcid PMC7012345 --output output/results.csv
  python cli.py --pmcids PMC7012345 PMC6543210 --output output/results.xlsx --nlp
  python cli.py --pmcid-file pmcids.txt --output output/results.xlsx
  python cli.py --html-dir data/sample_papers --output output/results.csv
        """
    )

    # Input options (mutually exclusive group)
    input_group = parser.add_mutually_exclusive_group(required=True)
    input_group.add_argument(
        "--pmcid",
        type=str,
        help="Single PMCID to process (e.g. PMC7012345)"
    )
    input_group.add_argument(
        "--pmcids",
        nargs="+",
        type=str,
        help="One or more PMCIDs to process"
    )
    input_group.add_argument(
        "--pmcid-file",
        type=str,
        help="Path to a text file with one PMCID per line"
    )
    input_group.add_argument(
        "--html-dir",
        type=str,
        help="Directory of pre-downloaded .html files to process (skips downloading)"
    )

    # Output options
    parser.add_argument(
        "--output",
        type=str,
        default="output/papers.csv",
        help="Output file path (.csv or .xlsx). Default: output/papers.csv"
    )
    parser.add_argument(
        "--save-html",
        type=str,
        default="data/sample_papers",
        help="Directory to cache downloaded HTML files. Default: data/sample_papers"
    )

    # Feature flags
    parser.add_argument(
        "--nlp",
        action="store_true",
        help="Enable NLP enrichment (age groups, diseases, accession codes, etc.)"
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=1.5,
        help="Seconds between HTTP requests (be polite!). Default: 1.5"
    )

    return parser.parse_args()


def load_pmcids_from_file(filepath: str) -> list:
    """Read PMCIDs from a text file, one per line."""
    with open(filepath, "r") as f:
        return [line.strip() for line in f if line.strip()]


def load_html_from_dir(html_dir: str) -> dict:
    """Load all .html files from a directory as {pmcid: html_string}."""
    html_dict = {}
    for fname in os.listdir(html_dir):
        if fname.endswith(".html"):
            pmcid = fname.replace(".html", "")
            fpath = os.path.join(html_dir, fname)
            html_dict[pmcid] = load_html_from_file(fpath)
            print(f"[cli] Loaded {fpath}")
    return html_dict


def main():
    args = parse_args()

    # ── Step 1: Get HTML ────────────────────────────────────────────────────
    if args.html_dir:
        print(f"[cli] Loading HTML files from {args.html_dir}...")
        html_dict = load_html_from_dir(args.html_dir)

    else:
        # Determine PMCID list
        if args.pmcid:
            pmcids = [args.pmcid]
        elif args.pmcids:
            pmcids = args.pmcids
        elif args.pmcid_file:
            pmcids = load_pmcids_from_file(args.pmcid_file)

        print(f"[cli] Fetching {len(pmcids)} paper(s)...")
        html_dict = fetch_multiple(pmcids, save_dir=args.save_html, delay=args.delay)

    if not html_dict:
        print("[cli] No papers to process. Exiting.")
        sys.exit(1)

    # ── Step 2: Parse ───────────────────────────────────────────────────────
    print(f"[cli] Parsing {len(html_dict)} paper(s)...")
    papers = parse_multiple(html_dict)

    # ── Step 3: Extract fields ──────────────────────────────────────────────
    print("[cli] Extracting fields...")
    records = extract_fields_multiple(papers)

    # ── Step 4: NLP enrichment (optional) ──────────────────────────────────
    if args.nlp:
        print("[cli] Running NLP enrichment...")
        records = enrich_records_with_nlp(records)

    # ── Step 5: Export ──────────────────────────────────────────────────────
    output_path = export(records, args.output)
    print(f"\n✅ Done! Output saved to: {output_path}")
    print(f"   Papers processed: {len(records)}")


if __name__ == "__main__":
    main()
