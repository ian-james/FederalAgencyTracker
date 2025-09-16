import sys
from pathlib import Path
from app_arguments import build_parser
from downloader import download_pdf
from pattern_files import load_patterns_from_file
from searching import SearchContext, search_pdf_text

# This main will download a file and search for whatever is in the context.
def main() -> None:
    ap = build_parser()
    args = ap.parse_args()

    pdf_path = download_pdf(
        args.url,
        out_dir=args.out_dir,
        timeout=args.timeout,
        overwrite=args.overwrite,
    )

    patterns = load_patterns_from_file(args.targets)
    if not patterns :
        print("No patterns to search for. Exiting.")
        return

    matches = search_pdf_text( search_context= SearchContext(
        pdf_path=pdf_path,
        ignore_case=not args.case_sensitive,
        exit_on_first=False,
        patterns=patterns,
        snippet_length=args.snippet_length,
        results_file= Path(args.results_file) if args.results_file else None,
    ))

    if not matches:
        print(f"No matches found in {pdf_path}.")
        return

    print(f"Found {len(matches)} matches in {pdf_path}:")
    for m in matches:
        print(f"- p.{m['page']:>3} | {m['pattern']!r} | …{m['snippet']}…")

def test_main():
    sys.argv = [
        "main.py",
        "https://public-inspection.federalregister.gov/2025-15819.pdf",
        "--out-dir", "./test_downloads",
        "--targets", "./search_args/test_regex.txt",
        "--results-file", "./results/test_results.txt",
        "--overwrite",
        "--snippet-length", "60",
        "--case-sensitive",

    ]
    main()

if __name__ == "__main__":
    test_main()
