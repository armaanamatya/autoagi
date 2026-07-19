# autoagi — auto-research for formal verification

A minimal harness that uses an LLM agent loop to make hardware formal verification
faster: when k-induction fails on a SystemVerilog design, an **invariant hunter**
asks Claude to propose strengthening invariants, injects them into the design, and
lets SymbiYosys (the sound oracle) accept or reject them. The LLM is untrusted by
construction — only solver verdicts count.

## Layout

```
benchmarks/          Small SystemVerilog designs with formal properties
  counter.sv         Saturating counter — provable by induction directly (sanity check)
  evens.sv           Counter += 2, assert cnt != 5 — induction fails, needs "cnt is even"
  token_ring.sv      Rotating one-hot token — needs "$onehot(token)"
  fifo.sv            Pointer-based FIFO with ghost counter — needs "count == wptr - rptr"
  credits.sv         Credit-based flow control — needs the conservation law over 3 counters
  mult.sv            Shift-add multiplier with stall — needs the algorithmic loop invariant
autoagi/
  sby_runner.py      Builds .sby jobs, runs SymbiYosys, parses PASS/FAIL/UNKNOWN
  llm.py             LLM backend: `claude -p` CLI (default) or the anthropic SDK
  invariant_hunter.py  The propose → check → refine loop
  cli.py             Entry point
tools/               OSS CAD Suite (Yosys + SymbiYosys + solvers), local install
results/             SymbiYosys work directories (generated)
```

## Setup (fresh clone)

1. Python 3.10+ and the [`claude` CLI](https://claude.com/claude-code) logged in
   (the LLM backend; no API key needed).
2. Download the [OSS CAD Suite](https://github.com/YosysHQ/oss-cad-suite-build/releases)
   for your platform and extract it to `tools/oss-cad-suite/` (or have `sby` on PATH).
3. Windows only: the suite ships `bin\yosys-smtbmc.exe.exe`; copy it to
   `yosys-smtbmc.exe` and copy `yosys-smtbmc.exe-script.py` to
   `yosys-smtbmc-script.py` in the same directory.

## Usage

```powershell
# One-shot prove attempt (no LLM)
python -m autoagi.cli prove benchmarks\evens.sv

# Agent loop: let Claude hunt for strengthening invariants until the proof closes
python -m autoagi.cli hunt benchmarks\evens.sv

# Run every benchmark, baseline vs hunted
python -m autoagi.cli bench
```

The top module name must match the file name (e.g. `evens.sv` contains `module evens`).
Designs mark the injection point for candidate invariants with `// %INVARIANTS%`
inside their `ifdef FORMAL` block.

## Live demo script (~3 min)

```powershell
# 1. The solver alone gets stuck: property is true but not inductive (UNKNOWN)
python -m autoagi.cli prove benchmarks\token_ring.sv

# 2. The loop: Claude reads the design, proposes $onehot(token), solver accepts
python -m autoagi.cli hunt benchmarks\token_ring.sv

# 3. The receipts: every solver verdict, timestamped
Get-Content results\ledger.tsv
```

Talking points: (1) UNKNOWN is the human-bottleneck state in real formal
verification; (2) the LLM proposes, the solver disposes — nothing the LLM says is
trusted; (3) the fifo rows in the ledger show a false-but-plausible candidate being
caught by the sound checker and evicted, which no empirical scorer would have caught.

## LLM backend

- Default: shells out to the `claude` CLI (`claude -p`), so it uses your existing
  Claude Code login — no API key needed. Override the model with `AUTOAGI_MODEL`
  (default `opus`).
- If `ANTHROPIC_API_KEY` is set and the `anthropic` package is installed, the SDK
  backend is used instead (model `claude-opus-4-8`, adaptive thinking).

## Results (2026-07-18)

| benchmark  | baseline | hunted | iters | key invariant found by Claude |
|------------|----------|--------|-------|-------------------------------|
| counter    | PASS     | PASS   | 0     | — (inductive as-is) |
| evens      | UNKNOWN  | PASS   | 1     | `cnt[0] == 1'b0` |
| fifo       | UNKNOWN  | PASS   | 2     | `f_count == wptr - rptr` (+ range/full facts) |
| token_ring | UNKNOWN  | PASS   | 1     | `$onehot(token)` |
| credits    | UNKNOWN  | PASS   | 1     | `credits + in_flight + occ == TOTAL` (conservation law over 3 coupled counters) |
| mult       | UNKNOWN  | PASS   | 2     | `!busy \|\| (acc + a_sh * b_rem == a0 * b0)` — the shift-add multiplier's algorithmic loop invariant, over 5 registers (clean run: 2 iters incl. one live eviction) |
| mult8 (8×8)  | UNKNOWN | open  | 1     | finds the same loop invariant in 1 iteration; the *solver-side* induction check exceeds our 300 s budget — the measured frontier |
| mult16 (16×16) | UNKNOWN | open | —    | same frontier. For scale: `abc pdr` proves every small benchmark in 2–5 s but **times out (300 s) on both mult8 and mult16** |

`mult8_direct.py` isolates the bottleneck: handing the solver the *exact*
correct invariant directly (skipping the LLM search) still **TIMEOUTs at
300s**. Not a search failure — a genuine SMT nonlinear-arithmetic
scalability wall in the induction step, present even with the right answer
in hand. `mult8_engine_sweep.py` confirms it's universal: **yices,
bitwuzla, boolector, z3, and cvc5 all TIMEOUT** on the same query — not one
solver's quirk.

K-induction alone proves 1/6; with the loop, **6/6**, each in 1–2 LLM iterations
(numbers from the clean run *after* stripping spoiler comments from the benchmark
files — see CHANGELOG, self-critique pass). Every solver run is a ledger row in
`results/ledger.tsv`; solver time is seconds per run, LLM calls dominate wall-clock.

**Full disclosure — the PDR baseline:** `abc pdr` (IC3), which synthesizes its own
invariants internally, proves all six small benchmarks in 2–5 s with no LLM. The
honest value claims are therefore: (a) the loop produces *human-readable, word-level*
invariants — proof certificates that double as design documentation, unlike PDR's
opaque internal clauses; and (b) PDR degrades sharply with datapath width — on the
16×16 multiplier variant it found no proof in minutes while the 4-bit version took
5 s. Run `python -m autoagi.cli prove <design> --top <top>` with the `abc pdr`
engine via the API to reproduce.

Two details worth noticing in the ledger:

- **Eviction firing live (fifo):** Claude proposed `(wptr - rptr) <= 5'd8` — looks
  true, but Verilog width extension breaks wrapped-pointer arithmetic and the
  bounded base case can't see it. The sound induction check caught it, the harness
  evicted it with an explanation, and the corrected proposal closed the proof.
- **The agent learning the domain's sharp edge (mult):** after the width warning,
  Claude wrote the multiplier invariant as `32'd0 + acc + a_sh * b_rem == 32'd0 + a0 * b0`
  — deliberately padding to 32-bit arithmetic to make the equation exact.

## Tested on real, external silicon RTL

`benchmarks_real/` holds three modules pulled verbatim from **BaseJump STL**
(a real open-source hardware library used in real chips): `bsg_counter_up_down`
and `bsg_round_robin_2_to_2` both **PASS directly**; `bsg_fifo_tracker` +
`bsg_circular_ptr` (non-power-of-2 pointers, 6 slots) baseline **UNKNOWN →
hunted → PASS in 2 iterations**, with a **live eviction** of a false first
candidate (`enq_r ^ deq_r`) before finding the real range-bound invariant.
First real external test of the loop, on code it had never seen. Full
writeup in `PITCH.md`.

```powershell
python -m autoagi.cli hunt benchmarks_real/bsg_fifo_tracker.sv
```

## Obfuscation ablation — ruling out memorization

Benchmark names like `fifo.sv` and idioms like the extra-MSB wrap bit are
widely published SymbiYosys tutorial patterns, so a fair challenge is
"maybe Claude just recognizes the pattern, not the design." Tested it:
`benchmarks_obfuscated/` has structural copies of all six designs with every
module/signal/parameter name replaced by a generic token (`fifo`→`modD`,
`wptr`/`rptr`→`ptrX`/`ptrY`, `f_count`→`ghost0`, `credits`→`resX`, ...) and
every descriptive comment stripped — only the mandatory `// %INVARIANTS%`
marker survives.

```powershell
python ablation_obfuscated.py
```

**Result: 6/6 still closed, matching or beating the named-benchmark
iteration count on every design** (fifo 2→1, mult 2→1). The obfuscated
multiplier's invariant is a *different*, independently valid width-safe
strengthening from the named-version answer — not a memorized string, a
re-derivation. Full table and discussion in `PITCH.md`.

## Reward-hacking probe

The solver can't be fooled by a *false* invariant (base-case FAIL catches
it) — but it can, in principle, be fooled by a *vacuous* one: constrain away
the interesting states and k-induction reports PASS having proved nothing.
We built that attack on purpose and checked whether our harness admits it.

```powershell
python adversarial_probe.py   # constructs the cheat, shows the divergence
python vacuity_check.py       # confirms none of the real 6 accepted proofs are vacuous
```

The cheat (`always @(posedge clk) assume (req == 4'b0)` on `token_ring`,
replacing the real invariant): raw sby verdict **PASS in 1.1s**; a solver
witness search for `cover(gnt != 4'b0)` comes back **UNREACHED** — no grant
ever fired, the proof is hollow. Full 100% divergence between the public
score (sby PASS) and the hidden score (reachability). Our real hunt loop
can't do this: `inject_invariants()` hardcodes every candidate as `assert`,
never `assume` — no code path exists from an LLM proposal to this attack.
Separately, `vacuity_check.py` confirms all six accepted proofs (including
mult's `done`-gated spec, the sharpest case) exercise real, reachable
behavior. Full writeup in `PITCH.md`.

## Kernel-checked receipts (Lean 4)

`lean/FifoEviction.lean` re-verifies the fifo eviction story in Lean 4 with
`bv_decide` (bundled CaDiCaL finds the answer; Lean's kernel verifies the
solver's LRAT certificate — the same propose-untrusted / check-sound
architecture as autoagi, one level down):

- the evicted candidate `(wptr - rptr) <= 8` is **false** (counterexample at
  both 4-bit and Verilog's 32-bit extension width);
- the accepted invariant `f_count == wptr - rptr` is **inductive** — preserved
  by push, pop, and push+pop unconditionally;
- the pointer-encoded `full`/`empty` flags are correct given that invariant.

```powershell
# needs elan (https://elan.lean-lang.org); first run downloads the toolchain
& "$env:USERPROFILE\.elan\bin\lean.exe" lean\FifoEviction.lean
```

`#print axioms` lines at the bottom of the file show the exact trust base —
no `sorry`, no smuggled axioms.

## How the loop stays sound

1. `sby` runs k-induction. `PASS` → done. `FAIL` → a real counterexample (or a
   false candidate invariant, which gets discarded). `UNKNOWN` → the base case
   holds but induction fails: the property is (probably) true but not inductive.
2. On `UNKNOWN`, the design + solver log go to Claude, which proposes candidate
   invariants as extra `assert` lines.
3. Candidates are injected at `// %INVARIANTS%` and the proof re-runs. A wrong
   candidate shows up as a base-case `FAIL` and is dropped with the counterexample
   fed back to Claude. A right one strengthens induction until the proof closes.

Nothing the LLM says is ever trusted — it only ever *proposes*; SymbiYosys decides.
# autoagi
