"""CLI entry point.

    python -m autoagi.cli prove benchmarks\\evens.sv     one-shot k-induction attempt
    python -m autoagi.cli hunt  benchmarks\\evens.sv     LLM invariant-hunting loop
    python -m autoagi.cli bench                          run all benchmarks
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .invariant_hunter import hunt
from .sby_runner import PROJECT_ROOT, prove, sby_available, summarize_log


def _top_of(path: Path) -> str:
    return path.stem


def cmd_prove(args) -> int:
    path = Path(args.design)
    top = args.top or _top_of(path)
    result = prove(path.read_text(encoding="utf-8"), top, label="cli", depth=args.depth)
    print(f"{top}: {result.status} ({result.elapsed_s:.1f}s)")
    if result.status in ("ERROR", "FAIL"):
        print(summarize_log(result.log))
    return 0 if result.status == "PASS" else 1


def cmd_hunt(args) -> int:
    path = Path(args.design)
    top = args.top or _top_of(path)
    outcome = hunt(path, top, max_iters=args.iters, depth=args.depth)
    print()
    print(f"=== {top}: {outcome.status} after {outcome.iterations} iteration(s) ===")
    if outcome.invariants:
        print("invariants:")
        for inv in outcome.invariants:
            print(f"  assert ({inv});")
    return 0 if outcome.status == "PASS" else 1


BENCH_SETS = {
    "all": None,  # every .sv in benchmarks/
    "hillclimb": ["counter", "evens", "fifo", "credits"],
    "holdout": ["token_ring", "mult"],
}


def cmd_bench(args) -> int:
    bench_dir = PROJECT_ROOT / "benchmarks"
    selected = BENCH_SETS.get(args.set)
    rows = []
    for path in sorted(bench_dir.glob("*.sv")):
        top = _top_of(path)
        if selected is not None and top not in selected:
            continue
        outcome = hunt(path, top, max_iters=args.iters, depth=args.depth)
        rows.append((top, outcome))
        print()
    print(f"{'benchmark':<12} {'baseline':<9} {'final':<9} {'iters':<6} invariants")
    for top, o in rows:
        base = o.baseline.status if o.baseline else "-"
        invs = "; ".join(o.invariants) if o.invariants else "-"
        print(f"{top:<12} {base:<9} {o.status:<9} {o.iterations:<6} {invs}")

    if args.metrics:
        closed = sum(1 for _, o in rows if o.status == "PASS")
        iters = sum(o.iterations for _, o in rows)
        print(f"METRIC proofs_closed={closed}")
        print(f"METRIC benchmarks={len(rows)}")
        print(f"METRIC total_llm_iterations={iters}")
        print(f"METRIC score={closed * 100 - iters}")
    return 0 if all(o.status == "PASS" for _, o in rows) else 1


def main() -> int:
    parser = argparse.ArgumentParser(prog="autoagi")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("prove", help="one-shot k-induction attempt")
    p.add_argument("design")
    p.add_argument("--top")
    p.add_argument("--depth", type=int, default=10)
    p.set_defaults(fn=cmd_prove)

    p = sub.add_parser("hunt", help="LLM invariant-hunting loop")
    p.add_argument("design")
    p.add_argument("--top")
    p.add_argument("--iters", type=int, default=5)
    p.add_argument("--depth", type=int, default=10)
    p.set_defaults(fn=cmd_hunt)

    p = sub.add_parser("bench", help="run benchmarks (baseline + hunt)")
    p.add_argument("--iters", type=int, default=5)
    p.add_argument("--depth", type=int, default=10)
    p.add_argument("--set", choices=sorted(BENCH_SETS), default="all",
                   help="hillclimb = optimize against these; holdout = generalization check")
    p.add_argument("--metrics", action="store_true",
                   help="emit METRIC name=value lines (pi-evo-research / Harbor format)")
    p.set_defaults(fn=cmd_bench)

    args = parser.parse_args()

    if not sby_available():
        print(
            "SymbiYosys not found. Install the OSS CAD Suite into tools\\oss-cad-suite\n"
            "(https://github.com/YosysHQ/oss-cad-suite-build/releases) or put sby on PATH.",
            file=sys.stderr,
        )
        return 2

    return args.fn(args)


if __name__ == "__main__":
    raise SystemExit(main())
