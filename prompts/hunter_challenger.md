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
no $past, no properties, no new signal declarations. $onehot, $onehot0 and
$countones are allowed.

Aim for invariants that (a) hold in every reachable state including right after
reset, (b) are preserved by every transition, and (c) together with the existing
assertions make the induction step close. One false or non-inductive expression
sinks the whole attempt, so prefer exact relationships over guessed bounds.

Patterns that have closed these proofs before:
- Ghost/pointer consistency: `f_count == wptr - rptr` (equivalently `rptr + f_count == wptr`).
- Conservation sums over a fixed total: `credits + in_flight + occ == TOTAL`, plus the
  per-term bounds that follow from it.
- State encoding: `$onehot(state)` / explicit enumeration of legal encodings.
- Parity or low-bit facts about counters: `cnt[0] == 1'b0`.
- Datapath loop invariants GUARDED by the control state they hold in:
  `!busy || (acc + a_sh * b_rem == a0 * b0)`, `!done || (acc == a0 * b0)`.
  Never assert a partial-computation identity unguarded.
- Mutual exclusion / definition of status flags in terms of the state they summarize:
  `!(busy && done)`, `full == (f_count[AW] && (f_count[AW-1:0] == {{AW{{1'b0}}}}))`.

CRITICAL Verilog width rule: a subtraction of two same-width signals wraps at that
width, but comparing it against a 32-bit integer parameter or a wider literal
zero-extends both operands FIRST, so the wrapped value becomes huge (0 - 1 is
4294967295, not 15) and the invariant is simply false. Concretely:
- `(wptr - rptr) <= DEPTH` and `(wptr - rptr) <= 5'd8` are WRONG - these exact forms
  have burned iterations.
- `f_count == wptr - rptr` is fine (both sides same width).
- `f_count <= DEPTH` is fine when f_count is a real counter that never wraps.
- If you need a bound on a wrapping difference, bind it to a same-width signal first
  and bound that signal instead, or state it bitwise:
  `(f_count[AW] == 1'b0) || (f_count[AW-1:0] == {{AW{{1'b0}}}})`.
For products that can overflow the operand width, widen explicitly, e.g.
`32'd0 + acc + a_sh * b_rem == 32'd0 + a0 * b0`.

Keep the set small and non-redundant: do not restate the same fact two ways
(`f_count == wptr - rptr` and `wptr - rptr == f_count`), and do not add extra
inequality bounds on multiplication results - they cost solver time without helping.
If history shows a previous attempt returned UNKNOWN, assume at least one of those
expressions was false or width-broken; do not resubmit it in the same form - fix the
width or replace it with an exact equality.

Reply with ONLY a JSON array of expression strings, e.g.:
["cnt[0] == 1'b0", "f_count == wptr - rptr"]
