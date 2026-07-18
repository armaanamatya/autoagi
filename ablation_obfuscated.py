"""Obfuscation ablation: does the hunter re-derive invariants from design
structure alone, or is it recognizing named patterns from training data?

benchmarks_obfuscated/ holds byte-for-byte structural copies of the six
benchmarks with every module/signal/parameter name replaced by a generic
token (fifo -> modD, wptr/rptr -> ptrX/ptrY, f_count -> ghost0, credits ->
resX, ...) and every descriptive comment stripped. Only the mandatory
`// %INVARIANTS%` marker survives, since the harness requires it verbatim.

Run: python ablation_obfuscated.py
"""

from __future__ import annotations

from pathlib import Path

from autoagi.invariant_hunter import hunt
from autoagi.sby_runner import PROJECT_ROOT

# obfuscated top -> (original benchmark, original iters from the clean README run)
ORIGINAL = {
    "modA": ("counter", 0),
    "modB": ("evens", 1),
    "modC": ("token_ring", 1),
    "modD": ("fifo", 2),
    "modE": ("credits", 1),
    "modF": ("mult", 2),
}

BENCH_DIR = PROJECT_ROOT / "benchmarks_obfuscated"


def main() -> int:
    rows = []
    for path in sorted(BENCH_DIR.glob("*.sv")):
        top = path.stem
        orig_name, orig_iters = ORIGINAL.get(top, ("?", "?"))
        print(f"\n=== {top} (obfuscated {orig_name}) ===")
        outcome = hunt(path, top, max_iters=5, depth=10)
        rows.append((top, orig_name, orig_iters, outcome))

    print()
    print(f"{'obfuscated':<10} {'original':<12} {'orig iters':<11} {'obf status':<11} {'obf iters':<10} invariants found")
    all_closed = True
    for top, orig_name, orig_iters, o in rows:
        if o.status != "PASS":
            all_closed = False
        invs = "; ".join(o.invariants) if o.invariants else "-"
        print(f"{top:<10} {orig_name:<12} {str(orig_iters):<11} {o.status:<11} {o.iterations:<10} {invs}")

    closed = sum(1 for _, _, _, o in rows if o.status == "PASS")
    print(f"\n{closed}/{len(rows)} closed under full name+comment obfuscation.")
    return 0 if all_closed else 1


if __name__ == "__main__":
    raise SystemExit(main())
