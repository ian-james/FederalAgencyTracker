#!/usr/bin/env python3
import argparse, io, json, tempfile
from pathlib import Path
from typing import Dict, Any, Iterable, List, Optional

import pendulum
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from tqdm import tqdm

from searching import SearchContext, search_pdf_text
from pattern_files import load_patterns_from_file


USER_AGENT = "frcrawler/0.1 (+https://example.com/contact)"


def make_session() -> requests.Session:
    s = requests.Session()
    s.headers.update({"User-Agent": USER_AGENT, "Accept": "*/*"})
    retry = Retry(
        total=5,
        backoff_factor=0.4,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET"],
        raise_on_status=False,
    )
    s.mount("https://", HTTPAdapter(max_retries=retry))
    s.mount("http://", HTTPAdapter(max_retries=retry))
    return s


def iter_jsonl(path: Path) -> Iterable[Dict[str, Any]]:
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError:
                print(f"[WARN] bad JSON line (skipped): {line[:120]!r}")


def fetch_pdf_bytes(session: requests.Session, url: str, timeout: float = 60.0, max_mb: Optional[int] = 50) -> bytes:
    r = session.get(url, stream=True, timeout=timeout)
    r.raise_for_status()
    out = io.BytesIO()
    size = 0
    for chunk in r.iter_content(1024 * 32):
        if not chunk:
            continue
        out.write(chunk)
        size += len(chunk)
        if max_mb and size > max_mb * 1024 * 1024:
            raise RuntimeError(f"PDF over size limit ({max_mb} MB)")
    return out.getvalue()

def setup_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Selective PDF downloader using existing search engine")
    ap.add_argument("--input", type=Path, required=True, help="Path to fr_new.jsonl")
    ap.add_argument("--targets", type=Path, required=True, help="Patterns file (one regex per line)")
    ap.add_argument("--keywords", nargs="*", default=[], help="Extra inline patterns (optional)")
    ap.add_argument("--case_sensitive", action="store_true", help="Default: ignore case")
    ap.add_argument("--snippet", type=int, default=80, help="Snippet padding chars")
    ap.add_argument("--exit_on_first", action="store_true", help="Stop scanning a PDF after first hit")
    ap.add_argument("--outdir", default="../results", help="Base output dir (dated subfolder created)")
    ap.add_argument("--tz", default="America/Glace_Bay", help="Timezone for dated folder")
    ap.add_argument("--max", type=int, default=None, help="Max docs to consider")
    ap.add_argument("--timeout", type=float, default=60.0)
    ap.add_argument("--max_pdf_mb", type=int, default=50)
    ap.add_argument("-o", "--output", default="selected.jsonl", help="Summary filename")
    return ap.parse_args()

def main():
    args = setup_args()

    # Load patterns via your helper
    patterns = load_patterns_from_file(args.targets)
    patterns.extend(args.keywords or [])
    if not patterns:
        raise SystemExit("No patterns provided (targets file empty and no --keywords).")

    # Dated output dirs
    stamp = pendulum.now(args.tz).to_date_string()
    run_dir = Path(args.outdir) / stamp
    pdf_dir = run_dir / "pdfs_selected"
    run_dir.mkdir(parents=True, exist_ok=True)
    pdf_dir.mkdir(parents=True, exist_ok=True)
    out_index = run_dir / args.output

    sess = make_session()
    seen = saved = 0

    with out_index.open("w", encoding="utf-8") as idx, tqdm(desc="Scanning PDFs") as pbar:
        for d in iter_jsonl(args.input):
            if args.max is not None and seen >= args.max:
                break
            seen += 1

            pdf_url = d.get("pdf_url")
            if not pdf_url:
                continue

            try:
                pdf_bytes = fetch_pdf_bytes(sess, pdf_url, timeout=args.timeout, max_mb=args.max_pdf_mb)
            except Exception as e:
                print(f"[WARN] fetch failed: {pdf_url} ({e})")
                pbar.update(1)
                continue

            # Write to a temp file so your SearchContext can use a path
            with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
                tmp_path = Path(tmp.name)
                tmp.write(pdf_bytes)

            # Search with your engine
            ctx = SearchContext(
                pdf_path=tmp_path,
                patterns=patterns,
                ignore_case=not args.case_sensitive,
                exit_on_first=args.exit_on_first,
                snippet_length=args.snippet,
            )
            try:
                results = search_pdf_text(ctx)  # -> list[dict]: page, pattern, snippet, span
            finally:
                # If no match, remove the temp file. If match, we’ll move it below.
                pass

            if results:
                # Final destination filename (from URL path)
                name = Path(pdf_url.split("?")[0]).name or "document.pdf"
                if not name.lower().endswith(".pdf"):
                    name += ".pdf"
                final_path = pdf_dir / name

                # Move temp → final
                try:
                    tmp_path.replace(final_path)
                except Exception:
                    # On cross-device move, fallback to copy+unlink
                    final_path.write_bytes(tmp_path.read_bytes())
                    tmp_path.unlink(missing_ok=True)

                # Summarize
                unique_patterns = []
                seen_p = set()
                first_snippets: Dict[str, str] = {}
                for r in results:
                    p = r["pattern"]
                    if p not in seen_p:
                        seen_p.add(p)
                        unique_patterns.append(p)
                        first_snippets[p] = r["snippet"]

                idx.write(json.dumps({
                    "document_number": d.get("document_number"),
                    "title": d.get("title"),
                    "publication_date": d.get("publication_date"),
                    "html_url": d.get("html_url"),
                    "pdf_url": pdf_url,
                    "pdf_path": str(final_path),
                    "rules_hit": unique_patterns,
                    "first_snippets": first_snippets,  # pattern -> first snippet
                    "hit_count": len(results),
                }, ensure_ascii=False) + "\n")
                idx.flush()
                saved += 1
            else:
                # No hits: remove temp file
                tmp_path.unlink(missing_ok=True)

            pbar.update(1)

    print(f"[DONE] Considered {seen} docs, saved {saved} matching PDFs.")
    print(f"[INFO] Index → {out_index}")
    print(f"[INFO] PDFs  → {pdf_dir}/")


if __name__ == "__main__":
    main()
