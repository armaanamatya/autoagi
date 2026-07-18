/-
  FifoEviction.lean — the autoagi fifo eviction story, kernel-checked.

  During the hunt on benchmarks/fifo.sv (4-bit pointers incl. wrap bit, DEPTH = 8),
  Claude proposed the candidate invariant

      (wptr - rptr) <= 8        -- "occupancy can't exceed depth" — looks true

  It is false: bitvector subtraction wraps, so for wptr = 0, rptr = 1 the
  difference is 15 (or 2^32 - 1 under Verilog's 32-bit self-determined
  extension). SymbiYosys evicted it via an induction-step FAIL. The corrected
  proposal, f_count == wptr - rptr, closed the proof.

  This file re-checks both facts in Lean 4 with bv_decide: an untrusted SAT
  solver (bundled CaDiCaL) finds the answer, and Lean's kernel verifies the
  solver's LRAT certificate — the same propose-untrusted / check-sound
  architecture as autoagi itself, one level down.

  Trust base note: bv_decide proofs that go through SAT depend on one
  per-proof native axiom (`<name>._native.bv_decide.ax_*` — the verified LRAT
  checker runs compiled); goals bv_decide closes by normalization alone use
  only Lean's three standard axioms. The #print axioms lines at the bottom
  display this honestly.
-/
import Std.Tactic.BVDecide

namespace Autoagi.Fifo

/-! ## 1. The evicted candidate is false -/

/-- The counterexample the solver found, at the pointers' own width:
    `0 - 1` wraps to 15, which is not `≤ 8`. -/
theorem trap_counterexample : ¬((0#4 : BitVec 4) - 1#4 ≤ 8#4) := by bv_decide

/-- The candidate `(wptr - rptr) ≤ 8` does not hold for all pointer values. -/
theorem trap_is_false : ∃ w r : BitVec 4, ¬(w - r ≤ 8#4) :=
  ⟨0#4, 1#4, trap_counterexample⟩

/-- Same trap at Verilog's 32-bit extension width — the form in which the
    candidate was actually evaluated, invisible to the bounded base case. -/
theorem trap_false_at_verilog_width : ¬((0#32 : BitVec 32) - 1#32 ≤ 8#32) := by
  bv_decide

/-! ## 2. The accepted invariant `f_count == wptr - rptr` is inductive

The identity is preserved by every transition of the FIFO unconditionally —
no side conditions on full/empty needed — which is exactly why it closes the
k-induction proof. -/

/-- Reset state satisfies the invariant. -/
theorem ghost_inv_init : (0#4 : BitVec 4) = 0#4 - 0#4 := by bv_decide

/-- Push: `wptr` and `f_count` both increment. -/
theorem ghost_inv_push (c w r : BitVec 4) (h : c = w - r) :
    c + 1 = (w + 1) - r := by bv_decide

/-- Pop: `rptr` increments, `f_count` decrements. -/
theorem ghost_inv_pop (c w r : BitVec 4) (h : c = w - r) :
    c - 1 = w - (r + 1) := by bv_decide

/-- Simultaneous push + pop: occupancy unchanged. -/
theorem ghost_inv_push_pop (c w r : BitVec 4) (h : c = w - r) :
    c = (w + 1) - (r + 1) := by bv_decide

/-! ## 3. What the trap was reaching for, recovered soundly

The range fact is true — but only *through* the ghost counter, never as a
free-standing fact about the pointers. -/

theorem range_via_ghost (c w r : BitVec 4) (h₁ : c = w - r) (h₂ : c ≤ 8#4) :
    w - r ≤ 8#4 := by bv_decide

/-! ## 4. Bonus: the pointer-encoded status flags agree with occupancy

`empty = (wptr == rptr)` and `full = (wptr == {~rptr[3], rptr[2:0]})`
(top-bit flip = XOR 8) are correct encodings, given the ghost invariant. -/

theorem empty_iff (c w r : BitVec 4) (h : c = w - r) :
    (w = r) ↔ c = 0#4 := by bv_decide

theorem full_iff (c w r : BitVec 4) (h : c = w - r) :
    (w = r ^^^ 8#4) ↔ c = 8#4 := by bv_decide

/-! ## Guard: no `sorry`, no smuggled axioms -/

#print axioms trap_is_false
#print axioms ghost_inv_push
#print axioms full_iff

end Autoagi.Fifo
