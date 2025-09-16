#!/usr/bin/env python3
"""
Fetch newest Federal Register documents via the official API.

Examples:
  # All docs published since yesterday (local time)
  poetry run python fr_new_docs.py --since yesterday -o fr_today.jsonl

  # Docs in date window
  poetry run python fr_new_docs.py --since 2025-09-01 --until 2025-09-08 -o week.jsonl

  # Filter by agency (repeat --agency to add more)
  poetry run python fr_new_docs.py --since 2025-09-01 --agency "Environmental Protection Agency" -o epa.jsonl
"""

from __future__ import annotations
import argparse, json, time
from typing import Iterable
import pendulum
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
# add near the top with other imports
from pathlib import Path
import pendulum


API_BASE = "https://www.federalregister.gov/api/v1"
DOCS_URL = f"{API_BASE}/documents.json"
USER_AGENT = "frcrawler/0.1 (+https://example.com/contact)"

def make_session() -> requests.Session:
    s = requests.Session()
    s.headers.update({"User-Agent": USER_AGENT, "Accept": "application/json"})
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

def fetch_new_documents(
    session: requests.Session,
    since: str,
    until: str | None = None,
    agencies: list[str] | None = None,
    per_page: int = 1000,
    max_pages: int = 2,
    sleep: float = 0.2,
) -> Iterable[dict]:
    """
    Yields newest->older documents with publication_date >= since (and <= until if provided).
    API returns at most ~2000 results per query (max_pages*per_page). Use tighter date windows for more.
    """
    page = 1
    fields = [
        "document_number", "title", "abstract",
        "html_url", "pdf_url", "publication_date", "agencies", "type"
    ]
    while page <= max_pages:
        params = {
            "order": "newest",
            "per_page": per_page,
            "page": page,
            # Date filters
            "conditions[publication_date][gte]": since,
        }
        if until:
            params["conditions[publication_date][lte]"] = until
        # ask only for fields we need
        for f in fields:
            params.setdefault("fields[]", []).append(f)
        # agencies filter (repeat param)
        if agencies:
            for a in agencies:
                # repeating the same key is fine; requests encodes it as multiple query params
                params.setdefault("conditions[agencies][]", []).append(a)

        r = session.get(DOCS_URL, params=params, timeout=30)
        r.raise_for_status()
        data = r.json()
        results = data if isinstance(data, list) else data.get("results") or data.get("documents") or []
        if not results:
            break

        for d in results:
            yield {
                "document_number": d.get("document_number"),
                "title": d.get("title"),
                "abstract": d.get("abstract"),
                "html_url": d.get("html_url"),
                "pdf_url": d.get("pdf_url"),
                "publication_date": d.get("publication_date"),
                "agencies": d.get("agencies"),
                "type": d.get("type"),
            }

        page += 1
        time.sleep(sleep)

def parse_date_arg(s: str, tz: str) -> str:
    """
    Accepts YYYY-MM-DD or the word 'yesterday'/'today' in your local TZ.
    Returns YYYY-MM-DD.
    """
    if s.lower() in {"yesterday", "today"}:
        now = pendulum.now(tz)
        d = now.date() if s.lower() == "today" else (now - pendulum.duration(days=1)).date()
        return d.to_date_string()
    # assume YYYY-MM-DD
    return pendulum.parse(s).to_date_string()
def main():
    parser = argparse.ArgumentParser(description="Fetch newest Federal Register documents via API")
    parser.add_argument("-o", "--output", default="fr_new.jsonl", help="Output JSONL filename (not path)")
    parser.add_argument("--since", default="yesterday",
                        help="Earliest publication_date (YYYY-MM-DD | 'yesterday' | 'today')")
    parser.add_argument("--until", default=None,
                        help="Latest publication_date (YYYY-MM-DD); default = open-ended (today)")
    parser.add_argument("--agency", action="append", help="Filter by agency name (repeatable)")
    parser.add_argument("--per_page", type=int, default=1000)
    parser.add_argument("--max_pages", type=int, default=2,
                        help="API returns at most ~2000 results per query; bump pages if needed")
    parser.add_argument("--tz", default="America/Glace_Bay",
                        help="Your local timezone for 'today/yesterday' (IANA name)")
    parser.add_argument("--outdir", default="../results",
                        help="Base output directory; script creates a dated subfolder here")
    args = parser.parse_args()

    # Resolve dates
    since = parse_date_arg(args.since, args.tz)
    until = parse_date_arg(args.until, args.tz) if args.until else None

    # Build ../results/YYYY-MM-DD and ensure it exists
    date_stamp = pendulum.now(args.tz).to_date_string()  # e.g., "2025-09-08"
    base_dir = Path(args.outdir)
    out_dir = base_dir / date_stamp
    out_dir.mkdir(parents=True, exist_ok=True)

    out_path = out_dir / args.output

    s = make_session()
    n = 0
    with open(out_path, "w", encoding="utf-8") as f:
        for doc in fetch_new_documents(
            s, since=since, until=until, agencies=args.agency,
            per_page=args.per_page, max_pages=args.max_pages
        ):
            f.write(json.dumps(doc, ensure_ascii=False) + "\n")
            n += 1

    print(f"Wrote {n} documents to {out_path} (publication_date >= {since}{' and <= ' + until if until else ''})")

if __name__ == "__main__":
    main()
