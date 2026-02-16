from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any, Iterable, Optional

from .bootstrap import load_index
from .inspect import categories_rows, discounts_rows, items_rows, prices_rows, summary


def _write_json(path: Path, obj: Any) -> None:
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")


def _write_jsonl(path: Path, rows: Iterable[dict]) -> None:
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False, default=str))
            f.write("\n")


def _write_csv(path: Path, rows: list[dict]) -> None:
    with path.open("w", newline="", encoding="utf-8") as f:
        if not rows:
            # Write an empty file with no header.
            return
        fieldnames = list(rows[0].keys())
        w = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow(r)


def export_all(inp: str = "data/dataset.json", out_dir: str = "out") -> None:
    idx = load_index(inp)
    outp = Path(out_dir)
    outp.mkdir(parents=True, exist_ok=True)

    items = items_rows(idx)
    prices = prices_rows(idx)
    cats = categories_rows(idx)
    discs = discounts_rows(idx)
    summ = summary(idx)

    _write_csv(outp / "items.csv", items)
    _write_csv(outp / "prices.csv", prices)
    _write_csv(outp / "categories.csv", cats)
    _write_csv(outp / "discounts.csv", discs)

    _write_jsonl(outp / "items.jsonl", items)
    _write_jsonl(outp / "prices.jsonl", prices)
    _write_jsonl(outp / "categories.jsonl", cats)
    _write_jsonl(outp / "discounts.jsonl", discs)

    _write_json(outp / "summary.json", summ)


def main(argv: Optional[list[str]] = None) -> int:
    p = argparse.ArgumentParser(description="Export normalized inspection views (CSV/JSONL/summary).")
    p.add_argument("--in", dest="inp", default="data/dataset.json", help="Input dataset path (default: data/dataset.json)")
    p.add_argument("--out", dest="out", default="out", help="Output directory (default: out/)")
    args = p.parse_args(argv)

    export_all(inp=args.inp, out_dir=args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
