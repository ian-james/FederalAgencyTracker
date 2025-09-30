import argparse
from pathlib import Path


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description="Download a gov PDF and search for text.")
    ap.add_argument("url", help="PDF URL (e.g https://public-inspection.federalregister.gov/2025-15819.pdf",)
    ap.add_argument("--out-dir", type=Path, default=Path("./downloads"), help="Directory to save PDF")
    ap.add_argument("--overwrite", action="store_true", help="Force re-download even if file exists")
    ap.add_argument("--results-file", type=Path, default=Path("./results/results.txt"), help="File to save results")
    ap.add_argument("--timeout", type=float, default=60.0, help="HTTP timeout (seconds)")
    ap.add_argument("--targets",
                    type=Path,
                    default=Path("./search_args/test_regex.txt"),
                    help="File with patterns to search for"
    )
    ap.add_argument("--case-sensitive", action="store_true", help="Case sensitive search")
    ap.add_argument("--snippet-length", type=int, default=50, help="Number of characters to include in snippet")
    return ap