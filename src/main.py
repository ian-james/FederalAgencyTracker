import sys
from pathlib import Path
from app_arguments import build_parser
from downloader import download_pdf
from pattern_files import load_patterns_from_file
from searching import SearchContext, search_pdf_text

def main(argv=None) -> None:
    """
    Main entry point for the CLI. Can accept an optional argv list for testing.
    """
    ap = build_parser()
    args = ap.parse_args(argv)

    out_dir = Path(args.out_dir)
    filename = args.url.split("/")[-1]
    out_path = out_dir / filename

    # Download only if not present or overwrite is specified
    pdf_path = out_path
    if not out_path.exists() or args.overwrite:
        pdf_path = download_pdf(
            args.url,
            out_dir=args.out_dir,
            timeout=args.timeout,
            overwrite=args.overwrite,
        )

    patterns = load_patterns_from_file(args.targets)
    if not patterns:
        print("No patterns to search for. Exiting.")
        return

    matches = search_pdf_text(
        search_context=SearchContext(
            pdf_path=pdf_path,
            ignore_case=not args.case_sensitive,
            exit_on_first=False,
            patterns=patterns,
            snippet_length=args.snippet_length,
        ),
        results_file=Path(args.results_file) if args.results_file else None,
    )

    if not matches:
        print(f"No matches found in {pdf_path}.")
        return

    print(f"Found {len(matches)} matches in {pdf_path}:")
    for m in matches:
        print(f"- p.{m['page']:>3} | {m['pattern']!r} | …{m['snippet']}…")


if __name__ == "__main__":
    # Use real sys.argv[1:] when run as a script
    main(sys.argv[1:])
