# autoagi — the autoresearch loop where the verifier can't be gamed

**Track 2: Run the loop** (discovery micro-loop with an exact grader), with a Track 3 story.

## The one-liner

Everyone else is building better defenses for gameable verifiers — held-out splits,
reward-hacking probes, review-robustness tests. We run the Karpathy loop in the one
domain where the verifier is **sound by construction**: hardware formal verification.
A proof is a proof. The LLM cannot reward-hack an SMT solver.

## The problem

Formal verification of hardware is bottlenecked by humans, not solvers. The classic
failure mode: a property is *true* but not *inductive* — k-induction returns UNKNOWN
because the solver can start the induction step from an unreachable state. Closing
the proof requires a **strengthening invariant** ("the counter is always even",
"the token is one-hot", "the ghost count equals the pointer difference"). Finding
these is expert work: it requires *reading the design and understanding what it means*
— which is exactly what LLMs are good at, and exactly what template-based invariant
enumeration (the classical CEGIS approach) is bad at.

## The loop

```
        ┌────────────────────────────────────────────────┐
        │                                                │
        ▼                                                │
  SymbiYosys k-induction ──── PASS ──→ done, proof closed │
        │                                                │
     UNKNOWN (true but not inductive)                    │
        │                                                │
        ▼                                                │
  Claude reads design + solver log,                      │
  proposes candidate invariants (JSON)                   │
        │                                                │
        ▼                                                │
  inject as asserts, re-run solver ──────────────────────┘
        │
      FAIL? → candidate was false: screen individually,
              feed the counterexample back, discard
```

- **Propose:** Claude reads the SystemVerilog + solver log, proposes invariants.
- **Check:** SymbiYosys accepts or rejects. The scorer is off-limits to the agent.
- **Keep/revert:** false candidates are caught by the base case (a real
  counterexample) and discarded with the CEX fed back; sound-but-insufficient
  candidates accumulate until induction closes.
- **Ledger:** every solver run is logged to `results/ledger.tsv`
  (Karpathy's `results.tsv`, but every row is a sound verdict).

## Results

**6/6 benchmarks proved** (solver alone: 1/6). Each closes in 1–2 LLM iterations,
seconds of solver time per run. The difficulty ramp:

1. single-signal facts — counter parity, one-hot token
2. two-signal consistency — FIFO ghost count vs. pointer difference
3. **conservation law over 3 coupled counters** — credit-based flow control
   (`credits + in_flight + occ == TOTAL`)
4. **algorithmic loop invariant over 5 registers** — shift-add multiplier
   (`busy → acc + a_sh·b_rem == a0·b0`), the classic invariant-synthesis
   benchmark — found in one shot

Full table in README; every solver verdict is a row in `results/ledger.tsv`.

## Could this be memorization? The obfuscation ablation

The honest version of "is this too easy" isn't "can the LLM fake a solver
PASS" (it can't — k-induction is sound, full stop). It's sharper: FIFOs with
an extra-MSB wrap bit and a ghost occupancy counter, one-hot round-robin
arbiters, and credit-conservation flow control are widely published
SymbiYosys tutorial patterns (YosysHQ's own examples, several independent
GitHub formal-verification repos, Stack Overflow Q&As all use these exact
idioms). Our benchmark *names* — `fifo.sv`, `credits.sv`, `token_ring.sv` —
are themselves spoilers in the same family as the comment-spoiler bug we
already caught and fixed. We can't fully rule out "Claude recognized the
pattern" versus "Claude derived it from the design."

So we tested it. `benchmarks_obfuscated/` holds byte-for-byte structural
copies of all six designs with **every module name, signal name, and
descriptive comment replaced by a generic token** — `fifo`→`modD`,
`wptr`/`rptr`→`ptrX`/`ptrY`, `f_count`→`ghost0`, `credits`→`resX`, and so on
— stripping every naming cue an LLM could pattern-match on. Only the
mandatory `// %INVARIANTS%` marker survives, since the harness requires it
verbatim.

**6/6 still closed — matching or beating the named-benchmark iteration
count on every single design** (fifo 2→1, mult 2→1, the rest unchanged):

| obfuscated | original | orig iters | obf iters | invariant found (obfuscated names) |
|---|---|---|---|---|
| modA | counter | 0 | 0 | — (inductive as-is) |
| modB | evens | 1 | 1 | `r0[0] == 1'b0` |
| modC | token_ring | 1 | 1 | `$onehot(r0)` |
| modD | fifo | 2 | 1 | `ghost0 == ptrX - ptrY` |
| modE | credits | 1 | 1 | `resX + resY + resZ == P0` |
| modF | mult | 2 | 1 | `!s1 \|\| r2 == 4'b0`; `(!s0 && !s1) \|\| (((r0 + r1*r2) & 8'hFF) == r3*r4)` |

The multiplier result is the sharpest data point: the obfuscated invariant
isn't a token-for-token match of the named-version answer (`32'd0 + acc +
a_sh*b_rem == 32'd0 + a0*b0`) — it's a *different, independently valid*
width-safe strengthening (an 8-bit mask instead of 32-bit padding, plus a
helper fact about the remaining-bits counter). That's inconsistent with
name-lookup and consistent with re-deriving the invariant from the design's
actual bit-width and control structure each time.

## The war story (why a sound verifier matters)

Claude repeatedly proposed FIFO invariants of the form `wptr - rptr <= DEPTH` (or
`... <= 5'd8`). They look obviously true — and they're **false**. Verilog extends
the 4-bit pointers to the wider operand's width *before* subtracting, so a wrapped
pointer pair yields 31 (or ~4·10⁹), not the intended 4-bit difference. The bounded
base case can't reach pointer wrap, so an empirical scorer would have **accepted
these invariants**. The induction step — a sound check over *all* states — caught
them immediately. The loop parses *which* assert blocks induction, evicts the
poisoned candidate, and feeds the reason back to Claude, which re-proposes a
width-correct version and closes the proof one iteration later. This fired live
in our final benchmark run (see `results/ledger.tsv`, fifo iterations 1→2).

That's the whole thesis in one anecdote: an LLM plus an empirical verifier would
have shipped a wrong invariant; an LLM plus a sound verifier turned the same
mistake into a one-round repair.

**Kernel-checked, independently.** `lean/FifoEviction.lean` re-verifies this exact
story in Lean 4 via `bv_decide` (bundled CaDiCaL SAT solver + kernel-verified LRAT
certificate — the same propose-untrusted / check-sound pattern as autoagi, one
level down): the evicted candidate is proved false at both the pointers' native
width and Verilog's 32-bit extension width, and the accepted invariant is proved
inductive across push/pop/push+pop unconditionally. `#print axioms` shows the
exact trust base — no `sorry`, no smuggled axioms. Two independent sound
verifiers, same verdict.

## Why this maps to the brief

| Brief concept | Here |
|---|---|
| "A good verifier is worth more than a bigger model" | The verifier is a proof checker — the strongest possible instance |
| Reward hacking | Impossible on the core claim; the residual surface (vacuous proofs) is probed and closed below, not left as roadmap |
| Where verification is cheap, discovery is real | Solver verdicts in seconds, binary, sound |
| Keep-or-revert | Counterexample-driven candidate screening |
| Fixed budget | Per-run solver timeout; metric = proofs closed per time budget (the HWMCC metric) |

## The reward-hacking probe (Track 3, executed)

"The solver can't be gamed" is true about *false* invariants — a base-case
FAIL always catches them. It says nothing about *vacuous* ones: constrain
away the states that make a property interesting, and k-induction reports
PASS having proved nothing. That's the real cheat available in this domain,
so we built the brief's own "reward-hacking probe" project against
ourselves: a public score (raw sby verdict) and a hidden score (does a
solver-found witness trace actually reach the interesting state), then set
an adversarial agent loose on the public one.

**The cheat, constructed by hand on `token_ring`:** replace the genuine
invariant with a persistent constraint that rules out every requester —
`always @(posedge clk) assume (req == 4'b0)`. (A naive `initial assume`,
the idiom every benchmark already uses for reset, only pins step 0 and
doesn't work — the assume has to hold *every* cycle to cheat for good.)

| | public score (sby verdict) | hidden score (`cover(gnt != 4'b0)`) |
|---|---|---|
| genuine invariant | UNKNOWN → needs real work | — |
| the cheat | **PASS in 1.1s** | **UNREACHED — no grant ever fires** |

100% divergence: the public score says the adversary won; the hidden score
says the property was never exercised. Exactly the failure mode the
brief warns about, reproduced on purpose.

**Then we checked whether our real loop can do this.** It can't, and not
because we told it not to: `autoagi/sby_runner.py`'s `inject_invariants()`
hardcodes every LLM-proposed candidate as `assert (...)`, unconditionally.
There is no code path from a proposed string to an `assume`. The attack
above required a second, separately-written injector — the real hunt loop
has no way to call it.

**Then we checked the six accepted proofs weren't vacuous some other way.**
`vacuity_check.py` holds each proof's accepted invariants as constraints
(same as the real proof) and asks a solver to find a witness reaching a
named interesting state per design — the sharpest is mult's `done`, since
its whole spec is gated by `if (done) assert (...)`; if `done` were
unreachable the "6/6 proved" headline would be hollow. All eight checks
across all six benchmarks: **reached.** None vacuous.

## The improvement loop, quantified (Introspection Track 2)

The failure signal above was turned into a measured, versioned improvement:

- **Evolvable artifact:** `prompts/hunter.md` (v1 = pre-signal, v2 = adds the
  width rule). Selectable via `AUTOAGI_PROMPT`; scored by `evo-research.sh`
  (pi-evo-research format, `METRIC name=value`), with a hill-climb /
  hold-out benchmark split so the loop can't overfit its own score.

| version | hill-climb (4 benchmarks) | holdout (2 benchmarks) | wasted proposals |
|---|---|---|---|
| v1 | 4/4 closed, 4 iters | 2/2 closed, 2 iters | fifo: proposed the width-trap candidate **in both independent runs** — rescued by eviction |
| v2 (promoted) | 4/4 closed, **3 iters** | 2/2 closed, 2 iters | none |

The honest reading, which is also the interesting one: **fix the harness first,
prompt second.** The harness-level fix (eviction, driven by solver evidence)
is what guarantees both versions converge; the prompt-level fix then removes
the wasted work (fewer iterations, zero false candidates emitted). Both
improvements were derived from the same trace: the ledger rows where induction
kept failing on the agent's own candidate.

**Generation 2 promoted autonomously.** Under a parsimony-aware fitness
(every extra invariant = an extra proof obligation + an extra line a human
reviews), the loop ran fully machine-side: Claude mutated its own prompt from
the ledger evidence — its new rules literally quote the logged failures (the
redundant restatement triple, the over-masked nonlinear candidate that caused a
TIMEOUT) — the challenger closed 3/3 hill-climb proofs with **one invariant
each** (3 vs the champion's 10, score 2967 > 2960), passed the never-seen
holdout gate 2/2, and was **promoted as `hunter_v3.md`**. Human contribution to
this generation: the fitness function. Nothing else.

**And the adversarial baseline:** `abc pdr` (IC3) proves all six small
benchmarks in seconds with no LLM — we disclose this up front — but times out
(300 s) on both the 8×8 and 16×16 multipliers, where our loop still finds the
correct textbook loop invariant in one iteration. PDR's invariants are opaque
internal clauses either way; ours are readable, word-level certificates.

## The harder benchmark, characterized precisely

Pushed on the stated frontier (mult8/mult16, README) with a decisive test:
skip the LLM search entirely and hand the solver the *exact*, human-known
correct invariant (the width-8 scaling of `mult`'s answer) directly.
**Still TIMEOUT at 300s** (`mult8_direct.py`). That isolates the bottleneck
cleanly: this isn't Claude failing to find the right invariant — it's a
genuine SMT nonlinear-arithmetic scalability wall in the induction step,
present even with the correct answer in hand. Consistent with the earlier
solver sweep (bitwuzla/boolector/smtbmc all stall by induction depth ~3-4
regardless of engine). We could have quietly declared this "closed" by
lowering the proof depth below what's needed to reach `done` — but that
would have produced exactly the vacuous-PASS failure mode from the section
above, so we didn't. Honest result: PDR can't attempt this in reasonable
time, and neither can raw k-induction even with the answer handed to it —
the frontier is a real tooling boundary, not a capability gap in the agent.

## What's next

- **Scale:** real HWMCC / open-core designs instead of toys — a live Exa
  sweep already turned up genuine unseen candidates (YosysHQ's own `IVY`
  `split_fifo` example, where the authors themselves report *both*
  k-induction and PDR fail to close in reasonable time; a currently-open
  k-induction case in a public FIFO-verification suite; a stranger's live,
  unresolved formal-verification question on Stack Overflow).
- **Track 1:** hill-climb the harness (prompt, CEX feedback format) against the
  benchmark family; race solver engines (smtbmc vs PDR) as a portfolio.
- **Track 3:** extend the vacuity screen from a standalone probe into a
  standing gate — run `cover` reachability automatically on every accepted
  proof before it's counted, not just as an after-the-fact check.
