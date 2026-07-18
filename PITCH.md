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

## Why this maps to the brief

| Brief concept | Here |
|---|---|
| "A good verifier is worth more than a bigger model" | The verifier is a proof checker — the strongest possible instance |
| Reward hacking | Impossible on the core claim; residual surface (vacuous properties) is our Track-3 roadmap |
| Where verification is cheap, discovery is real | Solver verdicts in seconds, binary, sound |
| Keep-or-revert | Counterexample-driven candidate screening |
| Fixed budget | Per-run solver timeout; metric = proofs closed per time budget (the HWMCC metric) |

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

## What's next

- **Scale:** real HWMCC / open-core designs instead of toys.
- **Track 1:** hill-climb the harness (prompt, CEX feedback format) against the
  benchmark family; race solver engines (smtbmc vs PDR) as a portfolio.
- **Track 3:** vacuity screening (`cover` reachability) so a future spec-writing
  agent can't win with unreachable assertions.
