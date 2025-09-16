from typing import List
from pathlib import Path
import json


def load_patterns_from_file(file_path: Path) -> List[str]:
    patterns = []
    if not file_path.exists():
        print(f"Pattern file {file_path} does not exist.")
        return patterns

    with open(file_path, "r") as f:
        patterns = [line.strip() for line in f if line.strip()]

    return patterns


def write_patterns_to_file(patterns: List[str], out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(patterns, f, indent=2)
    print(f"Wrote {len(patterns)} patterns to {out_path}")