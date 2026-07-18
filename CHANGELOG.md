# Changelog — all built 2026-07-18 (AGI House Autoresearch Build Day)

Chronological log of what was built and why. Times are local (PT).

## ~13:00 — Scaffold
- Created project structure: `autoagi/` Python package, `benchmarks/`, README.
- `sby_runner.py`: builds SymbiYosys k-induction jobs, classifies PASS / FAIL /
  UNKNOWN (UNKNOWN = true-but-not-inductive, the human-bottleneck state).
- `llm.py`: Claude backend via `claude -p` CLI (no API key needed); anthropic SDK optional.
- `invariant_hunter.py`: the propose → check → keep/revert loop.
- 4 benchmarks: counter (sanity), evens, token_ring, fifo.
- Downloaded + installed OSS CAD Suite (Yosys + SymbiYosys + solvers, 317 MB).
- Fixed Windows quirk: suite ships `yosys-smtbmc.exe.exe`; created correctly
  named wrapper copy so sby can spawn it.

## ~13:45 — First closed proofs
- `counter`: PASS at baseline (sanity check good).
- `evens`: baseline UNKNOWN → hunter closed with `cnt[0] == 1'b0` in 1 iteration.
- Fixed JSON extraction bug: candidate expressions contain brackets
  (`cnt[0]`), switched to `JSONDecoder.raw_decode` scanning.

## ~13:50 — Failure signal → harness improvement #1 (eviction)
- Full bench: evens + token_ring PASS in 1 iter; **fifo stuck at UNKNOWN**.
- Root cause: Claude proposed `wptr - rptr <= DEPTH` — false under Verilog
  32-bit width extension for wrapped pointers, but invisible to the bounded
  base case. The candidate poisoned the accepted set permanently.
- Fix 1: parse *which* assert fails in the induction step (`failing_assert_line`),
  **evict** candidates that are themselves the blocker, feed the reason back to
  Claude in the next prompt.
- Fix 2 (prompt v2): added the CRITICAL width-extension rule to the hunter prompt.
- Result: fifo closes in 2 iterations, with the eviction firing live in the
  clean run (`(wptr - rptr) <= 5'd8` proposed → evicted → corrected → PASS).
- Added `results/ledger.tsv`: every solver verdict logged (timestamp, benchmark,
  iteration, action, status, solver seconds, invariants).

## ~14:10 — Harder benchmarks
- `credits.sv`: credit-based flow control; needs a conservation law over three
  coupled counters (`credits + in_flight + occ == TOTAL`). Closed in 1 iteration.
- `mult.sv`: shift-add multiplier; needs the algorithmic loop invariant over 5
  registers (`busy → acc + a_sh·b_rem == a0·b0`). Initially PASSed at baseline
  because 5-cycle episodes are shorter than induction depth 10 — added a `stall`
  (backpressure) input to make episodes unbounded and the property honestly
  non-inductive. Closed in 1 iteration.
- Observed transfer of learning: Claude wrote the mult invariant with explicit
  32-bit padding (`32'd0 + acc + ...`) — applying the width rule learned from
  the fifo failure. 6/6 benchmarks proved (solver alone: 1/6).

## ~14:40 — Introspection Track 2 integration (improvement loop)
- Externalized the hunter prompt to versioned files: `prompts/hunter_v1.md`
  (pre-width-rule), `prompts/hunter_v2.md` (with width rule),
  `prompts/hunter.md` (active/promoted). Selectable via `AUTOAGI_PROMPT`.
- `cli.py bench`: added `--set hillclimb|holdout|all` (hill-climb on
  counter/evens/fifo/credits, hold out token_ring/mult as the generalization
  check) and `--metrics` (emits `METRIC name=value` lines).
- `evo-research.sh` + `evo-research.checks.sh`: pi-evo-research integration —
  the population mutates `prompts/hunter.md`, this script scores it on the
  hill-climb set, checks guard the format placeholders.
- `llm.py`: added `pi -p` backend (`AUTOAGI_BACKEND=pi`); installed the Pi
  coding-agent harness.
- `CHANGELOG.md`: this file.

## ~15:10 — Measured A/B: the improvement loop, quantified
- Ran prompt v1 vs v2 on the hill-climb set (counter/evens/fifo/credits):
  - **v1**: 4/4 closed, 4 LLM iterations — fifo again proposed the width-trap
    candidate `(wptr - rptr) <= DEPTH` (reproducible failure pattern!) and was
    rescued by the harness-level eviction, needing 2 iterations.
  - **v2**: 4/4 closed, 3 LLM iterations — fifo one-shots with width-safe
    proposals; no eviction needed.
- Interpretation: two levels of improvement from one failure signal — the
  harness fix (eviction) guarantees recovery; the prompt fix (width rule)
  prevents the failure. Both were derived from the same solver-verdict traces.
- v2 promoted as `prompts/hunter.md` (the active recipe version).

## ~15:30 — Holdout generalization check + Pi status
- v1 on holdout (token_ring, mult): 2/2 closed, 1 iter each — mult's natural
  invariant doesn't involve a 32-bit parameter, so the width trap doesn't
  trigger there. Honest conclusion recorded in PITCH: eviction (harness fix)
  provides robustness; the prompt fix provides efficiency (v2 = 5 total iters
  and zero false candidates vs v1 = 6 iters with a reproducible width-trap
  proposal on fifo in both independent runs).
- Pi harness: installed, `AUTOAGI_BACKEND=pi` wired, user logged in via
  Claude Pro/Max OAuth — blocked only on Claude "extra usage" balance (Pi
  bills per-token outside plan limits). `claude` CLI backend remains default.
- README cleanup (deduplicated fifo paragraph).
