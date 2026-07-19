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

## ~15:50 — Open-sourced + autonomous evolution
- PR #1 merged to github.com/armaanamatya/autoagi (open-source requirement).
- `autoagi/evolve.py`: one-command Evo-style generation loop — Claude mutates
  the champion prompt guided by the failure ledger; champion vs challenger
  scored on the hill-climb subset by the sound verifier; strict-improvement
  promotion gated by a holdout generalization check the optimizer never sees.
- `demo.ps1`: canned 3-minute demo (prove → hunt → ledger → evolve).
- README: fresh-clone setup instructions.

## ~16:15 — First live evolution generation
- Run 1: challenger REJECTED by the format gate (literal Verilog braces broke
  the template contract) — the backpressure check caught a malformed mutation
  before any solver/LLM budget was spent. Added a deterministic repair pass
  (escape all braces, restore placeholders) to separate "bad mutation" from
  "formatting accident".
- Run 2 (end-to-end): mutation OK → champion 297 vs challenger 297 on the
  hill-climb subset → **champion retained** (strict-improvement rule; no churn
  on ties). Honest finding: the metric is saturated (3/3 closed, 1 iter each);
  the challenger was visibly leaner (5 invariants proposed vs the champion's 8),
  which the score doesn't reward — parsimony tiebreak and harder benchmarks are
  the logical next generation of the metric itself.

## ~17:00 — Self-critique pass (red-team before the judges do)
- **Found and fixed an answer leak:** benchmark header comments stated the needed
  invariant, and full design text (comments included) goes to the LLM. Stripped
  all five spoiler comments and re-ran the entire suite clean: **still 6/6**
  (6 total iterations; mult now takes 2 with a live eviction of a false a_sh
  range fact). The invariants are re-derived from design structure alone.
- **Ran the adversarial baseline ourselves:** `abc pdr` (IC3) proves all six
  original benchmarks in 2–5 s with no LLM — "solver alone: 1/6" is true only
  for k-induction/smtbmc and must be framed accordingly. Disclosed rather than
  discovered by a judge. On the new 16×16 multiplier, PDR ran 15+ minutes
  without a proof (vs 5 s at 4-bit) — the separation experiment.
- Added `--engine` support (any sby engine, e.g. `abc pdr`) to the runner.

## ~17:20 — Robustness + the autonomy experiment
- **Fixed a real harness bug the mult16 attempt exposed:** sby child processes
  inherit pipe handles on Windows, so pipe-based timeouts hang forever. run_sby
  now writes to a log file, kills the whole process tree on deadline, and
  returns a first-class TIMEOUT status (handled in the hunt loop: drop the
  trial, tell the LLM the constraints were too expensive).
- Added `mult8.sv` (8×8) as the difficulty hedge between mult and mult16.
- **Parsimony-aware evolution fitness** (1000/proof − 10/iteration − 1/invariant):
  every extra invariant is an extra proof obligation and an extra line a human
  must review, so a leaner certificate at equal coverage is strictly better.
  This de-saturates the metric that tied generation 1 — rerunning evolution
  to test for a fully autonomous promotion.

## ~18:20 — AUTONOMOUS PROMOTION (generation 2)
- PDR baselines locked: `abc pdr` TIMEOUT (300 s) on **both** mult8 and mult16
  (vs 2–5 s on every small benchmark). The width wall is measured, not asserted.
- Evolution generation 2, under the parsimony metric, end-to-end autonomous:
  - Claude **wrote** the challenger prompt from the ledger evidence. Its additions
    cite the actual logged failures: a no-redundant-restatement rule quoting the
    real `f_count == wptr - rptr` triple, a one-nonlinear-term rule quoting the
    real over-masked mult8 candidate that caused a TIMEOUT, and a
    cut-on-TIMEOUT history rule.
  - Challenger closed 3/3 hill-climb proofs with **one invariant each** (3 total
    vs the champion's 10). Score 2967 > 2960.
  - **Holdout gate passed 2/2** (token_ring and mult, one iteration each).
  - **PROMOTED as hunter_v3.md** — machine-authored, machine-scored,
    machine-gated. The only human contribution this generation: the fitness
    function.
- Evolution run 1 of the day had been rejected by an over-strict placeholder
  gate (exactly-once; `str.format` tolerates repeats) — relaxed to at-least-once.
- mult8/mult16 solver frontier: our route finds the correct loop invariant but
  yices times out verifying 16-bit nonlinear induction steps at depth 6; at
  depth 2 induction fails on window-start garbage states (`busy && done`).
  Solver sweep (bitwuzla/boolector, varying depth) in progress — honest status:
  the multiplier separation is PDR-fails-vs-we-find-the-invariant, with the
  final solver check still open at width 8+.

## ~18:35 — Lean 4 kernel-checked receipts
- `lean/FifoEviction.lean`: the fifo eviction story re-verified in Lean 4 via
  `bv_decide` (Lean ≥ 4.12: bundled CaDiCaL SAT solver + kernel-verified LRAT
  certificate — the propose-untrusted / check-sound pattern in miniature).
  Proved: the evicted candidate `(wptr - rptr) <= 8` is false (4-bit and
  32-bit Verilog-extension widths); the accepted `f_count == wptr - rptr` is
  inductive (push/pop/push+pop, unconditionally); `full`/`empty` pointer
  encodings correct given the invariant. `#print axioms` guard shows the
  exact trust base (three standard axioms + per-proof native LRAT axiom).
- Installed elan + Lean 4.32.0 stable; runs standalone, no mathlib, no lake
  project. Demo line: the failure signal itself is machine-verified by two
  independent sound checkers (SMT model checker at RTL, Lean kernel at the
  bitvector-algebra level).

## ~19:00 — Obfuscation ablation (ruling out memorization)
- Sharpened self-critique: benchmark names (`fifo`, `credits`, `token_ring`)
  and idioms (extra-MSB wrap-bit FIFO, one-hot arbiter, credit conservation)
  are widely published SymbiYosys tutorial patterns — a live Exa sweep
  turned up multiple independent GitHub repos and a Stack Overflow post
  using the identical idioms. Can't fully rule out pattern recognition vs.
  genuine derivation from the spoiler-comment fix alone.
- `benchmarks_obfuscated/`: byte-for-byte structural copies of all six
  designs, every module/signal/parameter name replaced by a generic token
  (`fifo`→`modD`, `wptr`/`rptr`→`ptrX`/`ptrY`, `f_count`→`ghost0`,
  `credits`→`resX`, ...), every descriptive comment stripped. Only the
  mandatory `// %INVARIANTS%` marker kept verbatim (harness requirement).
  `ablation_obfuscated.py` runs `hunt()` on all six standalone (no changes
  to the harness or the original benchmarks).
- **Result: 6/6 closed, matching or beating the named-benchmark iteration
  count on every design** (fifo 2→1, mult 2→1, rest unchanged). The
  obfuscated multiplier's invariant is a *different*, independently valid
  width-safe strengthening (8-bit mask + a remaining-bits helper fact) from
  the named-version answer (32-bit padding) — evidence of re-derivation,
  not string recall. Strongest single rebuttal to the "easy/memorized
  dataset" critique so far: full name+comment stripping caused zero
  regression. Written up in PITCH.md and README.md.

## ~19:20 — Reward-hacking probe + a harder benchmark, characterized honestly
- **Track 3, executed, not just claimed:** the real gap in "the solver
  can't be gamed" isn't false invariants (base-case FAIL catches those) —
  it's *vacuous* ones. Added `inject_covers` / `check_vacuity` (mode-cover
  reachability) to `sby_runner.py`, plus `inject_invariants_and_covers` to
  check an accepted proof's invariants-as-constraints alongside a
  reachability witness in one job.
- `vacuity_check.py`: ran on all six accepted proofs (invariants held as
  constraints, one or two named interesting states per design — mult's
  `done` is the sharpest, since its whole spec is gated by `if (done)
  assert(...)`). **All 8 checks across 6 benchmarks: REACHED.** None
  vacuous. (One false-alarm en route: `cover(cnt==10)` on `counter` came
  back UNREACHED at depth=12 — an off-by-one margin bug in the test's own
  depth budget, not a real finding; fixed by lowering the target, confirmed
  it was a test artifact.)
- `adversarial_probe.py`: constructed the actual cheat by hand on
  `token_ring` — replaced the real invariant with a persistent
  `always @(posedge clk) assume (req == 4'b0)`. Public score (sby verdict):
  **PASS in 1.1s**. Hidden score (`cover(gnt != 4'b0)`): **UNREACHED** — no
  grant ever fires, the proof is hollow. 100% public/hidden divergence,
  reproduced on purpose — exactly the brief's own "reward-hacking probe"
  project pattern, run against ourselves. (First attempt used `initial
  assume`, the idiom every benchmark already uses for reset — didn't cheat
  at all, since it only pins step 0; had to switch to a persistent assume
  to actually break the proof. Worth noting: the naive version of this
  attack doesn't even work.) Confirmed the real hunt loop has no code path
  to this attack: `inject_invariants()` hardcodes `assert` unconditionally.
- **mult8, characterized decisively:** `mult8_direct.py` hands the solver
  the width-8 scaling of `mult`'s known-correct invariant directly, no LLM
  search. **Still TIMEOUT at 300s.** Isolates the bottleneck cleanly: not a
  search failure, a genuine SMT nonlinear-arithmetic scalability wall in
  the induction step (matches the earlier solver sweep — bitwuzla /
  boolector / smtbmc all stall by induction depth ~3-4 regardless of
  engine). Could have "closed" this cheaply by shrinking proof depth below
  what's needed to reach `done` — declined, since that's exactly the
  vacuous-PASS failure mode from the probe above.
- Live Exa sweep for real next-tier benchmarks turned up genuine
  candidates: YosysHQ's own `IVY` `split_fifo` example (authors' own docs:
  both k-induction *and* PDR fail to close in reasonable time), a
  currently-open k-induction case in `billdmar/fifo-verification-suite`'s
  `async_fifo`, and a stranger's live, unresolved formal-verification
  question on Stack Overflow. Logged as future work, not attempted tonight
  (async/multi-clock designs don't fit the harness's single-clock
  assumption without real plumbing).
- All new capability is additive: no changes to the accepted-proof harness
  path, the original benchmarks, or the promoted prompt. Written up in
  PITCH.md and README.md.

## ~19:35 — mult8: five independent solvers, one universal wall
- `mult8_engine_sweep.py`: reran the direct-invariant test (correct answer
  handed to the solver, no LLM search) across every SMT backend bundled in
  the OSS CAD Suite. **yices, bitwuzla, boolector, z3, cvc5 — all five
  TIMEOUT at 300s.** Not one solver's quirk; a universal nonlinear-
  arithmetic wall at width 8, present even with the exact right answer in
  hand. Strengthens the honest-frontier claim from a single-engine result
  to a five-way-confirmed one.
- Also surfaced and highlighted (already present, underused): the
  autonomous generation-2 prompt diff. `hunter_v2.md` (human, 39 lines) vs.
  `hunter_v3.md`/`hunter.md` (Claude-authored, 63 lines, promoted after
  beating the champion 2967 > 2960 + holdout 2/2) shows Claude adding a
  "SOLVER-COST rules" section that quotes its own failure ledger verbatim
  — the exact redundant-restatement triple and the exact over-masked
  candidate that caused a real TIMEOUT. Verifiable evidence of harness
  self-improvement, not a generic-advice diff.

## ~19:50 — Tested on real, external silicon RTL (BaseJump STL)
- Researched formal-verification benchmark suites (HWMCC = gate-level, poor
  fit for a word-level LLM loop; found **HierSVA-DS**, a NeurIPS 2026
  Datasets & Benchmarks Track submission — 342 real, formally-verified
  modules from BaseJump STL with a measured 17.9% LLM-vacuity rate across
  12 frontier models, independent validation of tonight's reward-hacking
  probe). Cited in PITCH.md.
- Rather than adapt HierSVA's own generation-task format (different task
  shape from ours — assertion generation vs. strengthening a stuck
  property), pulled 3 small modules directly from BaseJump STL itself (the
  real RTL library HierSVA-DS is built from): `bsg_counter_up_down`,
  `bsg_fifo_tracker` + `bsg_circular_ptr`, `bsg_round_robin_2_to_2`. Logic
  kept verbatim; only `BSG_INV_PARAM` macros resolved to concrete values
  and our own FORMAL block added. `benchmarks_real/`.
- `bsg_counter_up_down` and `bsg_round_robin_2_to_2`: **PASS directly**
  under a realistic caller-contract assumption. `bsg_fifo_tracker`
  (non-power-of-2 circular pointers, 6 slots, to exercise the real
  wraparound-arithmetic branch): baseline FAIL until a realistic caller
  contract was added (matches how it's actually gated upstream) → baseline
  **UNKNOWN** → hunted → **PASS in 2 iterations**. Claude's first candidate
  (`enq_r ^ deq_r`) was **false, evicted live** — the first eviction of the
  night on code from outside this project. Second attempt: `rptr_r < 6`,
  `wptr_r < 6` (the same non-power-of-2 range-bound lesson `fifo.sv` taught
  it) plus a genuine pointer/latch coupling fact. Written up in PITCH.md
  and README.md.
