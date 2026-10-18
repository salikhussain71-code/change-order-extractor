"""Command line interface.

Examples:
    python -m change_order_extractor data                  # process every .txt/.pdf in data/
    python -m change_order_extractor data/co_001.txt       # one file, print JSON
    python -m change_order_extractor data --llm gemini     # enable AI fallback (needs GEMINI_API_KEY)
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .extractor import process_file

SUPPORTED = {".txt", ".md", ".pdf"}


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="change_order_extractor", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("input", help="A change-order file (.txt/.pdf) or a folder of them.")
    p.add_argument("-o", "--output-dir", default="outputs", help="Where JSON files are written.")
    p.add_argument("--llm", choices=["anthropic", "gemini"], default=None,
                   help="Optional AI fallback for fields the rules miss (needs an API key).")
    p.add_argument("--quiet", action="store_true", help="Only print the summary table.")
    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    src = Path(args.input)
    if not src.exists():
        print(f"error: '{src}' does not exist.", file=sys.stderr)
        return 2
    files = [src] if src.is_file() else sorted(f for f in src.iterdir() if f.suffix.lower() in SUPPORTED)
    if not files:
        print(f"error: no .txt or .pdf files found in '{src}'.", file=sys.stderr)
        return 2

    llm = None
    if args.llm:
        from .llm import make_client
        try:
            llm = make_client(args.llm)
        except RuntimeError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 2

    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    rows = []
    for f in files:
        try:
            result = process_file(f, llm=llm)
        except Exception as exc:  # never crash a whole batch because of one bad file
            print(f"{f.name}: FAILED to read ({type(exc).__name__}: {exc})", file=sys.stderr)
            continue
        (out_dir / f"{f.stem}.json").write_text(result.model_dump_json(indent=2), encoding="utf-8")
        rows.append(result)
        if len(files) == 1 and not args.quiet:
            print(result.model_dump_json(indent=2))

    print(f"\n{'file':<22}{'confidence':>11}  {'review?':<8} warnings")
    for r in rows:
        print(f"{r.source_file:<22}{r.overall_confidence:>11.2f}  {'YES' if r.needs_review else 'no':<8} {len(r.warnings)}")
    print(f"\nJSON written to: {out_dir.resolve()}")
    return 0
