You are helping close a k-induction proof for a SystemVerilog design.
The base case holds, but the induction step fails: the assertions are true but not
inductive on their own. Propose strengthening invariants.

Design ({top}.sv):
```systemverilog
{design}
```

Solver log (SymbiYosys, mode prove, engine smtbmc):
```
{log}
```

{history}

Propose 1-4 candidate strengthening invariants as SystemVerilog boolean
expressions over the design's signals (registers, wires, formal-block signals like
f_count). Each will be injected as:
    always @(posedge clk) if (f_past_valid) assert (<expr>);
so each expression must be a pure combinational condition on current-cycle values -
no $past, no properties, no new signal declarations. System functions that are pure
predicates on current values ($onehot, $countones) are allowed.

Aim for invariants that (a) hold from reset, (b) are preserved by every transition,
and (c) together with the existing assertions make the induction step close.

Patterns that have historically closed these proofs:
- ghost-counter / pointer identity: `f_count == wptr - rptr`
- conservation sum plus a bound on each term:
  `credits + in_flight + occ == TOTAL`, `in_flight <= TOTAL`, `occ <= TOTAL`
- parity or range facts on counters: `cnt[0] == 1'b0`
- one-hot state: `$onehot(token)`
- mutual exclusion of control flags: `!(busy && done)`
- combinational outputs tied to state: `empty == (f_count == 0)`, `gnt == (req & token)`
- loop-invariant for iterative datapaths, guarded by the active flag:
  `!busy || (acc + a_sh * b_rem == a0 * b0)`, `!done || (acc == a0 * b0)`

Emit a MINIMAL, non-redundant set. Do not restate one fact several ways
(`f_count == wptr - rptr` and `wptr - rptr == f_count` and `rptr + f_count == wptr`
are one invariant, not three). Extra near-duplicate conjuncts do not help the proof
and can push the solver into a timeout. Prefer 1-2 strong invariants over 4 weak ones.

Solver cost matters. Multiplying two non-constant signals is expensive and the cost
grows sharply with width: for datapaths wider than ~8 bits, emit at most ONE
product-bearing invariant and pair it only with cheap structural facts (flag
exclusion, shift alignment such as `!busy || (a_sh[k:0] == 0)`, monotone bounds,
`b_rem == 0` implying completion). Never add a masked restatement of a product
invariant you already emitted.

CRITICAL Verilog width rule: if an expression mixes narrow signals with a 32-bit
integer parameter (e.g. `wptr - rptr <= DEPTH`), the operands are zero-extended to
32 bits BEFORE the arithmetic, so wrap-around differences break (0 - 1 becomes
4294967295, not 15). Keep wrap-around arithmetic at the signal's own width: compare
against another same-width signal, slice explicitly, or bind the difference to a
same-width term first (e.g. `f_count == wptr - rptr` is fine because both sides are
4-bit; `wptr - rptr <= DEPTH` is NOT, and neither is `(wptr - rptr) <= 4'd8` unless
you have checked the width of every operand).

Read {history} before answering. Never repeat an expression that was already tried
and rejected. If a previous attempt returned UNKNOWN, one of your conjuncts was not
itself inductive - keep the ones that look sound and replace the suspect one, rather
than starting over. If a previous attempt TIMED OUT, the invariants were probably
sound but too expensive: resubmit a strictly smaller and cheaper set.

Reply with ONLY a JSON array of expression strings, e.g.:
["cnt[0] == 1'b0", "f_count == wptr - rptr"]
