# pdf_search_engine.py
import dataclasses
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Iterator, List, Dict, Optional, Protocol, Any, Tuple

import pymupdf

# =========================
# Context & DTOs
# =========================
@dataclass
class SearchContext:
    pdf_path: Path
    patterns: List[str] = field(default_factory=list)
    ignore_case: bool = True
    exit_on_first: bool = False
    snippet_length: int = 50
    page_start: Optional[int] = None   # 1-based inclusive
    page_end: Optional[int] = None     # 1-based inclusive
    # You can add more knobs later (e.g., max_matches, whole_word, etc.)


@dataclass
class MatchResult:
    page: int                       # 1-based
    pattern: str
    snippet: str
    span: Tuple[int, int]           # (start, end) in page text


# =========================
# Text Sources (Search "where")
# =========================

class TextSource(Protocol):
    """Provides page_number (1-based), text."""
    def iter_pages(self, ctx: SearchContext) -> Iterator[Tuple[int, str]]:
        ...


class PyMuPDFTextSource:
    """Reads text using PyMuPDF."""
    def __init__(self, pdf_path: Path):
        self.pdf_path = Path(pdf_path)

    def iter_pages(self, ctx: SearchContext) -> Iterator[Tuple[int, str]]:
        with pymupdf.open(self.pdf_path) as doc:
            total = len(doc)
            start = ctx.page_start or 1
            end = ctx.page_end or total
            # clamp
            start = max(1, min(start, total))
            end = max(1, min(end, total))
            for p in range(start, end + 1):
                page = doc.load_page(p - 1)  # PyMuPDF is 0-based
                yield p, page.get_text()


# =========================
# Search Strategies (Search "how")
# =========================

class SearchStrategy(Protocol):
    def find_matches(self, text: str) -> Iterator[Tuple[re.Pattern[str], re.Match[str]]]:
        ...


class RegexSearchStrategy:
    """Compiles user regexes (with optional IGNORECASE) and yields matches."""
    def __init__(self, patterns: List[str], ignore_case: bool = True):
        flags = re.IGNORECASE if ignore_case else 0
        compiled: List[re.Pattern[str]] = []
        for p in patterns:
            try:
                compiled.append(re.compile(p, flags))
            except re.error as e:
                print(f"[WARN] Skipping invalid regex {p!r}: {e}")
        if not compiled:
            raise ValueError("No valid patterns to search.")
        self._compiled = compiled

    def find_matches(self, text: str) -> Iterator[Tuple[re.Pattern[str], re.Match[str]]]:
        for pat in self._compiled:
            for m in pat.finditer(text):
                yield pat, m


# =========================
# Match Actions (Search "do")
# =========================

class MatchAction(Protocol):
    def on_match(self, result: MatchResult) -> None: ...
    def close(self) -> None: ...


class CollectingAction:
    """Stores matches in memory; retrieve via .results."""
    def __init__(self):
        self.results: List[Dict[str, Any]] = []

    def on_match(self, result: MatchResult) -> None:
        self.results.append(dataclasses.asdict(result))

    def close(self) -> None:
        pass


class PrintAction:
    """Prints each match as JSON to stdout."""
    def on_match(self, result: MatchResult) -> None:
        print(json.dumps(dataclasses.asdict(result), ensure_ascii=False))

    def close(self) -> None:
        pass


class JsonlFileAction:
    """Writes each match as a JSON line to a file."""
    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._fh = self.path.open("w", encoding="utf-8")

    def on_match(self, result: MatchResult) -> None:
        self._fh.write(json.dumps(dataclasses.asdict(result), ensure_ascii=False) + "\n")
        self._fh.flush()

    def close(self) -> None:
        try:
            self._fh.close()
        except Exception:
            pass


class CompositeAction:
    """Fan-out to multiple actions (e.g., collect + file)."""
    def __init__(self, actions: List[MatchAction]):
        self._actions = actions

    def on_match(self, result: MatchResult) -> None:
        for a in self._actions:
            a.on_match(result)

    def close(self) -> None:
        for a in self._actions:
            a.close()


# =========================
# Engine (Orchestrator)
# =========================

class SearchEngine:
    def __init__(self, text_source: TextSource, strategy: SearchStrategy, action: MatchAction):
        self.text_source = text_source
        self.strategy = strategy
        self.action = action

    @staticmethod
    def _make_snippet(text: str, start: int, end: int, pad: int) -> str:
        s = max(0, start - pad)
        e = min(len(text), end + pad)
        return text[s:e].replace("\n", " ")

    def run(self, ctx: SearchContext) -> List[Dict[str, Any]]:
        """Executes search; returns collected results if the action contains them."""
        collecting = isinstance(self.action, CollectingAction) or any(
            isinstance(a, CollectingAction) for a in getattr(self.action, "_actions", [])
        )

        try:
            for page_num, text in self.text_source.iter_pages(ctx):
                for pat, match in self.strategy.find_matches(text):
                    result = MatchResult(
                        page=page_num,
                        pattern=pat.pattern,
                        snippet=self._make_snippet(text, match.start(), match.end(), ctx.snippet_length),
                        span=(match.start(), match.end()),
                    )
                    self.action.on_match(result)
                    if ctx.exit_on_first:
                        self.action.close()
                        # If collecting, surface what we have so far:
                        if collecting:
                            if isinstance(self.action, CollectingAction):
                                return self.action.results
                            elif isinstance(self.action, CompositeAction):
                                for a in self.action._actions:
                                    if isinstance(a, CollectingAction):
                                        return a.results
                        return []
        finally:
            self.action.close()

        # Return collected results if present
        if collecting:
            if isinstance(self.action, CollectingAction):
                return self.action.results
            elif isinstance(self.action, CompositeAction):
                for a in self.action._actions:
                    if isinstance(a, CollectingAction):
                        return a.results
        return []


# =========================
# Convenience helper (matches your original entry point)
# =========================

def search_pdf_text(
    search_context: SearchContext,
    results_file: Optional[Path] = None,
    also_print: bool = False,
) -> List[Dict[str, Any]]:
    """
    High-level helper to keep your original API feel.
    - results_file: if provided, write JSONL there.
    - also_print: optionally mirror to stdout.
    - returns collected results as list[dict]
    """
    actions: List[MatchAction] = [CollectingAction()]
    if also_print:
        actions.append(PrintAction())
    if results_file:
        actions.append(JsonlFileAction(results_file))

    action = CompositeAction(actions) if len(actions) > 1 else actions[0]
    source = PyMuPDFTextSource(search_context.pdf_path)
    strategy = RegexSearchStrategy(search_context.patterns, ignore_case=search_context.ignore_case)
    engine = SearchEngine(source, strategy, action)
    return engine.run(search_context)
