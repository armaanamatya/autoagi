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
no $past, no properties, no new signal declarations.

Aim for invariants that (a) hold from reset, (b) are preserved by every transition,
and (c) together with the existing assertions make the induction step close.
Classic examples: parity/range facts about counters, one-hot-ness of state,
consistency between a ghost counter and pointer difference.

CRITICAL Verilog width rule: if an expression mixes narrow signals with a 32-bit
integer parameter (e.g. `wptr - rptr <= DEPTH`), the operands are zero-extended to
32 bits BEFORE the arithmetic, so wrap-around differences break (0 - 1 becomes
4294967295, not 15). Keep wrap-around arithmetic at the signal's own width: compare
against another same-width signal, slice explicitly, or bind the difference to a
same-width term first (e.g. `f_count == wptr - rptr` is fine because both sides are
4-bit; `wptr - rptr <= DEPTH` is NOT).

Reply with ONLY a JSON array of expression strings, e.g.:
["cnt[0] == 1'b0", "f_count == wptr - rptr"]
