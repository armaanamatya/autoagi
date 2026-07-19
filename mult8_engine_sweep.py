"""Does mult8 close under ANY available SMT backend with the correct
invariant supplied directly? mult8_direct.py already showed the default
(yices via smtbmc) times out at 300s with the right answer in hand -- this
sweeps every solver bundled in the OSS CAD Suite to see if the wall is
universal or backend-specific.

Usage: python mult8_engine_sweep.py <engine-string>
  e.g. python mult8_engine_sweep.py "smtbmc bitwuzla"
"""

from __future__ import annotations

import sys
import time

from autoagi.sby_runner import PROJECT_ROOT, inject_invariants, prove

engine = sys.argv[1] if len(sys.argv) > 1 else "smtbmc"
label = engine.replace(" ", "_").replace("-", "")

path = PROJECT_ROOT / "benchmarks" / "mult8.sv"
design_text = path.read_text(encoding="utf-8")

invariants = [
    "!busy || (acc + a_sh * b_rem == a0 * b0)",
    "!(busy && done)",
]

full = inject_invariants(design_text, invariants)
print(f"[{engine}] solving mult8 with the correct invariant (depth=10, timeout=300s)...")
t0 = time.monotonic()
result = prove(full, "mult8", label=f"sweep_{label}", depth=10, timeout_s=300, engine=engine)
print(f"[{engine}] status={result.status} elapsed={result.elapsed_s:.1f}s")
