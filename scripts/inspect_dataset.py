"""Generate the reproducible Phase 1 inspection report."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from moodshiftx.catalogue import CatalogueError, inspect_catalogue


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", default=str(ROOT / "data" / "fma_metadata"))
    parser.add_argument("--output", default=str(ROOT / "docs" / "dataset_inspection.json"))
    args = parser.parse_args()
    try:
        report = inspect_catalogue(args.data_dir)
    except CatalogueError as exc:
        parser.error(str(exc))
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    Path(args.output).write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, ensure_ascii=False))
    print(f"\nSaved report: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
