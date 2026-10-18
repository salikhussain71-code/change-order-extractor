"""Measure accuracy against hand-labelled answers and check whether confidence is meaningful.

    python -m change_order_extractor.evaluate data evaluation/labels.json
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from .extractor import process_file
from .models import FIELD_NAMES


def _same(a, b) -> bool:
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return abs(float(a) - float(b)) < 0.005
    return str(a).strip().lower() == str(b).strip().lower()


def evaluate(data_dir: Path, labels_path: Path, llm=None) -> dict:
    labels = json.loads(labels_path.read_text(encoding="utf-8"))
    per_field = {n: [0, 0] for n in FIELD_NAMES}  # correct, total
    right_conf, wrong_conf, mismatches = [], [], []
    for fname, expected in labels.items():
        res = process_file(data_dir / fname, llm=llm)
        for name in FIELD_NAMES:
            if name not in expected:
                continue
            exp, got = expected[name], res.fields[name].value
            ok = _same(exp, got) if exp is not None else got is None
            per_field[name][1] += 1
            per_field[name][0] += int(ok)
            if got is not None:
                (right_conf if ok else wrong_conf).append(res.fields[name].confidence)
            if not ok:
                mismatches.append((fname, name, exp, got))
    return {"per_field": per_field, "right_conf": right_conf, "wrong_conf": wrong_conf, "mismatches": mismatches}


def main(argv=None) -> int:
    argv = argv or sys.argv[1:]
    data_dir = Path(argv[0] if argv else "data")
    labels = Path(argv[1] if len(argv) > 1 else "evaluation/labels.json")
    r = evaluate(data_dir, labels)
    tot_c = sum(c for c, _ in r["per_field"].values())
    tot_n = sum(n for _, n in r["per_field"].values())
    print(f"{'field':<24}{'correct':>8}{'total':>7}{'accuracy':>10}")
    for name, (c, n) in r["per_field"].items():
        if n:
            print(f"{name:<24}{c:>8}{n:>7}{c / n:>10.0%}")
    print(f"{'OVERALL':<24}{tot_c:>8}{tot_n:>7}{tot_c / tot_n:>10.0%}")
    avg = lambda xs: (sum(xs) / len(xs)) if xs else float("nan")
    print(f"\nMean confidence when correct: {avg(r['right_conf']):.2f}  (n={len(r['right_conf'])})")
    print(f"Mean confidence when WRONG:   {avg(r['wrong_conf']):.2f}  (n={len(r['wrong_conf'])})")
    if r["mismatches"]:
        print("\nMismatches (file, field, expected, got):")
        for m in r["mismatches"]:
            print("  ", m)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
