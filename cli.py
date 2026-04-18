"""
cli.py
Command-line interface for PaperStand.

Usage:
    # One PMC paper → CSV
    python cli.py --pmcid PMC7012345

    # Multiple PMC papers → Excel
    python cli.py --pmcids PMC7012345 PMC6543210 --output output/results.xlsx

    # From a text file (one PMCID or URL per line)
    python cli.py --input-file pmcids.txt --output output/results.csv

    # Browser-saved HTML files (Nature, Cell, Science, etc.)
    python cli.py --html-dir data/sample_papers --output output/results.csv

    # Any URL (works for PMC + PLOS directly; others need browser-save)
    python cli.py --url "https://pmc.ncbi.nlm.nih.gov/articles/PMC7012345/"

    # Add regex NLP enrichment (age, species, diseases, sample counts)
    python cli.py --pmcid PMC7012345 --nlp

    # Export BERT-ready JSON for Group 2's ML pipeline
    python cli.py --pmcid PMC7012345 --output output/results.json --bert

    # Run PubMedBERT NER inference (requires: pip install transformers torch)
    python cli.py --pmcid PMC7012345 --output output/results.json --run-bert
"""

import argparse
import sys
import os

# Make sure paperstand package is importable when running from repo root
sys.path.insert(0, os.path.dirname(__file__))

from paperstand.fetcher   import fetch_batch, fetch_by_pmcid, fetch_by_url, load_from_dir
from paperstand.parsers   import get_parser
from paperstand.extractor import extract, extract_many
from paperstand.exporter  import save
from paperstand.nlp       import enrich_records, export_bert_inputs, run_pubmedbert


# ── Argument parsing ──────────────────────────────────────────────────────────

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="paperstand",
        description="Extract structured data from research papers into CSV/Excel/JSON.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    # ── Input (mutually exclusive) ────────────────────────────────────────────
    inp = p.add_mutually_exclusive_group(required=True)
    inp.add_argument(
        "--pmcid", type=str,
        help="Single PMCID (e.g. PMC7012345)",
    )
    inp.add_argument(
        "--pmcids", nargs="+",
        help="One or more PMCIDs",
    )
    inp.add_argument(
        "--url", type=str,
        help="Single article URL",
    )
    inp.add_argument(
        "--input-file", type=str,
        help="Text file with one PMCID or URL per line",
    )
    inp.add_argument(
        "--html-dir", type=str,
        help="Directory of pre-saved .html files (for Nature, Cell, Science, etc.)",
    )

    # ── Output ────────────────────────────────────────────────────────────────
    p.add_argument(
        "--output", "-o", type=str, default="output/papers.csv",
        help="Output path. Extension sets format: .csv / .xlsx / .json "
             "(default: output/papers.csv)",
    )
    p.add_argument(
        "--cache-dir", type=str, default="data/html_cache",
        help="Directory to cache downloaded HTML (default: data/html_cache)",
    )

    # ── NLP / ML ──────────────────────────────────────────────────────────────
    p.add_argument(
        "--nlp", action="store_true",
        help="Run regex NLP enrichment: age groups, species, diseases, "
             "sample counts, accession codes",
    )
    p.add_argument(
        "--bert", action="store_true",
        help="Export PubMedBERT-ready JSON for Group 2's ML pipeline "
             "(saves to output/bert_inputs.json)",
    )
    p.add_argument(
        "--run-bert", action="store_true",
        help="Actually run PubMedBERT NER inference "
             "(requires: pip install transformers torch)",
    )
    p.add_argument(
        "--bert-output", type=str, default="output/bert_inputs.json",
        help="Output path for BERT JSON (default: output/bert_inputs.json)",
    )

    # ── Fetch settings ────────────────────────────────────────────────────────
    p.add_argument(
        "--delay", type=float, default=1.5,
        help="Seconds between HTTP requests (default: 1.5)",
    )

    return p


# ── Main pipeline ─────────────────────────────────────────────────────────────

def main():
    args = build_parser().parse_args()

    # ── Step 1: Collect (html, url) pairs ────────────────────────────────────
    html_map = {}  # identifier → (html, url)

    if args.html_dir:
        print(f"[cli] Loading HTML files from {args.html_dir}...")
        html_map = load_from_dir(args.html_dir)

    elif args.pmcid:
        html, url = fetch_by_pmcid(args.pmcid, cache_dir=args.cache_dir, delay=args.delay)
        html_map[args.pmcid.upper()] = (html, url)

    elif args.pmcids:
        html_map = fetch_batch(args.pmcids, cache_dir=args.cache_dir, delay=args.delay)

    elif args.url:
        html, url = fetch_by_url(args.url, cache_dir=args.cache_dir, delay=args.delay)
        # Use last path segment as identifier
        identifier = args.url.rstrip("/").split("/")[-1] or "article"
        html_map[identifier] = (html, url)

    elif args.input_file:
        items = _read_input_file(args.input_file)
        html_map = fetch_batch(items, cache_dir=args.cache_dir, delay=args.delay)

    # Filter out failed fetches
    html_map = {k: v for k, v in html_map.items() if v[0]}
    if not html_map:
        print("[cli] No papers to process. Exiting.")
        sys.exit(1)

    # ── Step 2: Parse ─────────────────────────────────────────────────────────
    print(f"\n[cli] Parsing {len(html_map)} paper(s)...")
    papers = {}
    for identifier, (html, url) in html_map.items():
        parser = get_parser(html, url=url, identifier=identifier)
        papers[identifier] = parser.parse()

    # ── Step 3: Extract fields ────────────────────────────────────────────────
    print("[cli] Extracting fields...")
    records = extract_many(papers)

    # ── Step 4: NLP enrichment (optional) ────────────────────────────────────
    if args.nlp or args.bert or args.run_bert:
        print("[cli] Running NLP enrichment...")
        records = enrich_records(records)

    # ── Step 5: BERT export / inference (optional) ────────────────────────────
    if args.run_bert:
        print("[cli] Running PubMedBERT NER inference...")
        bert_out = args.bert_output.replace("inputs", "results")
        run_pubmedbert(records, output_path=bert_out)
    elif args.bert:
        print("[cli] Exporting BERT-ready JSON for Group 2...")
        export_bert_inputs(records, output_path=args.bert_output)
        print(f"[cli] BERT inputs → {args.bert_output}")

    # ── Step 6: Save main output ──────────────────────────────────────────────
    bert_ready = args.output.endswith(".json") and (args.bert or args.run_bert)
    output_path = save(records, args.output, bert_ready=bert_ready)

    # ── Summary ───────────────────────────────────────────────────────────────
    print(f"\n✅  Done!")
    print(f"    Papers processed : {len(records)}")
    print(f"    Output           : {output_path}")
    if args.bert or args.run_bert:
        bert_out = args.bert_output.replace("inputs", "results") if args.run_bert else args.bert_output
        print(f"    BERT JSON        : {bert_out}")


# ── Helpers ───────────────────────────────────────────────────────────────────

def _read_input_file(filepath: str) -> list:
    """Read PMCIDs or URLs from a text file, one per line."""
    with open(filepath, "r") as f:
        return [line.strip() for line in f if line.strip() and not line.startswith("#")]


if __name__ == "__main__":
    main()
