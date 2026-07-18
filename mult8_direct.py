"""Is mult8 stuck because the search hasn't found the right invariant, or
because the solver can't verify even the *correct* invariant at width 8?

Skip the LLM search: inject the width-8 scaling of the known-good mult.sv
answer directly and prove once. Decisive either way.
"""

from __future__ import annotations

import time
from pathlib import Path

from autoagi.sby_runner import PROJECT_ROOT, inject_invariants, prove

path = PROJECT_ROOT / "benchmarks" / "mult8.sv"
design_text = path.read_text(encoding="utf-8")

invariants = [
    "!busy || (acc + a_sh * b_rem == a0 * b0)",
    "!(busy && done)",
]

full = inject_invariants(design_text, invariants)
print("Invariants:", invariants)
print("Solving (depth=10, timeout=300s, default engine)...")
t0 = time.monotonic()
result = prove(full, "mult8", label="direct", depth=10, timeout_s=300)
print(f"status={result.status} elapsed={result.elapsed_s:.1f}s")
if result.status != "PASS":
    from autoagi.sby_runner import summarize_log
    print(summarize_log(result.log))
