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
combinational predicates ($onehot, $onehot0, $countones) are allowed and preferred
over hand-expanded case lists.

Aim for invariants that (a) hold from reset, (b) are preserved by every transition,
and (c) together with the existing assertions make the induction step close.
Classic examples: parity/range facts about counters, one-hot-ness of state,
consistency between a ghost counter and pointer difference, a conservation law
(sum of credits/in-flight/occupancy equals a constant), and for sequential
datapaths a loop invariant that pins the partial result plus a separate fact for
the terminal/done state.

CRITICAL Verilog width rule: if an expression mixes narrow signals with a 32-bit
integer parameter (e.g. `wptr - rptr <= DEPTH`), the operands are zero-extended to
32 bits BEFORE the arithmetic, so wrap-around differences break (0 - 1 becomes
4294967295, not 15). Keep wrap-around arithmetic at the signal's own width: compare
against another same-width signal, slice explicitly, or bind the difference to a
same-width term first (e.g. `f_count == wptr - rptr` is fine because both sides are
4-bit; `wptr - rptr <= DEPTH` is NOT).

SOLVER-COST rules - violating these causes UNKNOWN or TIMEOUT, which wastes a whole
iteration:
- Emit a minimal, non-redundant set. Do not restate the same fact in different
  syntax (`f_count == wptr - rptr` and `wptr - rptr == f_count` and
  `rptr + f_count == wptr` are one invariant, not three). Every extra expression
  costs solver time and buys nothing if it is implied by another.
- Nonlinear terms (signal * signal) are expensive and scale badly with width. Use
  AT MOST ONE invariant containing a variable-times-variable product, state it in
  its plainest form, and never wrap it in redundant masks or extra guards
  (`(((acc + a_sh*b_rem) & 16'hFFFF) == ((a0*b0) & 16'hFFFF)) || !busy` is strictly
  worse than `!busy || (acc + a_sh * b_rem == a0 * b0)`). Pair it with cheap
  bit-level or range facts (shift-register alignment, low bits zero, mutual
  exclusion of control flags) rather than with more arithmetic.
- If the history shows a previous attempt returned UNKNOWN or TIMEOUT, do not add
  more expressions on top. Cut the most expensive one, simplify the arithmetic, or
  replace a product with a structural fact about the same signals.
- Prefer one exact, cheap invariant over several weak guesses; single facts like
  `cnt[0] == 1'b0` or `$onehot(token)` close proofs in a fraction of the time.

Reply with ONLY a JSON array of expression strings, e.g.:
["cnt[0] == 1'b0", "f_count == wptr - rptr", "$onehot(token)"]
