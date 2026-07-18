"""The propose -> check -> refine loop.

When k-induction returns UNKNOWN (base case holds, induction step fails), the
property is probably true but not inductive. This loop asks Claude for candidate
strengthening invariants, injects them into the design's FORMAL block, and re-runs
the solver. False candidates surface as base-case FAILs and are discarded with the
counterexample fed back into the next round. The solver is the only judge.
"""

from __future__ import annotations

import datetime as _dt
import os
from dataclasses import dataclass, field
from pathlib import Path

from . import llm
from .sby_runner import (
    RESULTS_DIR,
    SbyResult,
    failing_assert_line,
    inject_invariants,
    prove,
    summarize_log,
)

LEDGER = RESULTS_DIR / "ledger.tsv"
_LEDGER_HEADER = "timestamp\tbenchmark\titeration\taction\tstatus\tsolver_s\tinvariants\n"


def _ledger_row(top: str, iteration: int | str, action: str, status: str, solver_s: float, invariants: list[str]):
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    if not LEDGER.exists():
        LEDGER.write_text(_LEDGER_HEADER, encoding="utf-8")
    ts = _dt.datetime.now().isoformat(timespec="seconds")
    inv = "; ".join(invariants) if invariants else "-"
    with LEDGER.open("a", encoding="utf-8") as f:
        f.write(f"{ts}\t{top}\t{iteration}\t{action}\t{status}\t{solver_s:.1f}\t{inv}\n")

_DEFAULT_PROMPT = Path(__file__).resolve().parent.parent / "prompts" / "hunter.md"


def _load_prompt_template() -> str:
    """Active hunter prompt; override with AUTOAGI_PROMPT for A/B and evo runs."""
    return Path(os.environ.get("AUTOAGI_PROMPT", _DEFAULT_PROMPT)).read_text(encoding="utf-8")


@dataclass
class HuntOutcome:
    status: str                       # final sby status
    invariants: list[str]             # invariants in play at the end
    iterations: int
    baseline: SbyResult | None = None
    history: list[str] = field(default_factory=list)


def hunt(design_path: Path, top: str, max_iters: int = 5, depth: int = 10, log=print) -> HuntOutcome:
    design_text = design_path.read_text(encoding="utf-8")

    log(f"[{top}] baseline prove (no extra invariants)...")
    baseline = prove(design_text, top, label="baseline", depth=depth)
    log(f"[{top}] baseline: {baseline.status} in {baseline.elapsed_s:.1f}s")
    _ledger_row(top, 0, "baseline", baseline.status, baseline.elapsed_s, [])

    if baseline.status == "PASS":
        return HuntOutcome(status="PASS", invariants=[], iterations=0, baseline=baseline)
    if baseline.status == "FAIL":
        log(f"[{top}] base case fails - real counterexample, no invariant can fix this.")
        return HuntOutcome(status="FAIL", invariants=[], iterations=0, baseline=baseline)
    if baseline.status == "ERROR":
        log(f"[{top}] sby error - check the log:\n{summarize_log(baseline.log)}")
        return HuntOutcome(status="ERROR", invariants=[], iterations=0, baseline=baseline)

    # UNKNOWN: induction fails -> hunt for strengthening invariants
    accepted: list[str] = []
    history: list[str] = []
    last = baseline

    for it in range(1, max_iters + 1):
        log(f"[{top}] iteration {it}: asking Claude for strengthening invariants...")
        history_text = (
            "Previous attempts and results:\n" + "\n".join(history)
            if history
            else "This is the first attempt."
        )
        current_design = inject_invariants(design_text, accepted) if accepted else design_text
        prompt = _load_prompt_template().format(
            top=top,
            design=current_design,
            log=summarize_log(last.log),
            history=history_text,
        )
        try:
            reply = llm.ask(prompt)
            proposed = llm.extract_json_list(reply)
        except llm.LLMError as e:
            log(f"[{top}] LLM error: {e}")
            history.append(f"- (iteration {it}) LLM response unparseable; retrying.")
            continue

        proposed = [p.strip() for p in proposed if p.strip()][:4]
        log(f"[{top}] proposed: {proposed}")

        trial = accepted + [p for p in proposed if p not in accepted]
        result = prove(inject_invariants(design_text, trial), top, label=f"iter{it}", depth=depth)
        log(f"[{top}] with {len(trial)} invariant(s): {result.status} in {result.elapsed_s:.1f}s")
        _ledger_row(top, it, "trial", result.status, result.elapsed_s, trial)

        if result.status == "PASS":
            return HuntOutcome(status="PASS", invariants=trial, iterations=it, baseline=baseline, history=history)

        if result.status == "FAIL":
            # Some candidate is actually false (base case broke). Test candidates
            # individually against the base case and keep only the survivors.
            survivors = []
            for p in proposed:
                if p in accepted:
                    continue
                single = prove(
                    inject_invariants(design_text, accepted + [p]), top,
                    label=f"iter{it}_screen", depth=depth,
                )
                _ledger_row(top, it, "screen", single.status, single.elapsed_s, [p])
                if single.status == "FAIL":
                    history.append(f"- REJECTED (fails on a reachable state): {p}")
                    log(f"[{top}]   rejected false candidate: {p}")
                else:
                    survivors.append(p)
                    if single.status == "PASS":
                        return HuntOutcome(
                            status="PASS", invariants=accepted + [p], iterations=it,
                            baseline=baseline, history=history,
                        )
            accepted += survivors
            last = result
            continue

        # UNKNOWN: base case still holds but induction fails. Find WHICH assert
        # blocks the induction step. If it's one of our own candidates, evict it:
        # it is either false beyond the base-case depth (classic cause: Verilog
        # width-extension wraparound) or unsupported â€” either way it poisons the set.
        fail_line = failing_assert_line(result, top)
        evicted = None
        if fail_line:
            for cand in trial:
                if cand in fail_line:
                    evicted = cand
                    break
        if evicted:
            trial = [c for c in trial if c != evicted]
            log(f"[{top}]   evicted candidate (induction fails on it): {evicted}")
            history.append(
                f"- EVICTED '{evicted}': the induction step fails on this candidate itself. "
                "It is likely FALSE on deep reachable states (check Verilog width-extension: "
                "mixing narrow signals with 32-bit parameters extends operands to 32 bits, "
                "breaking wrap-around arithmetic) or it needs more support. Fix or replace it."
            )
        elif fail_line:
            history.append(f"- kept {proposed}, but induction still fails on: {fail_line}")
        else:
            history.append(f"- kept but not sufficient (induction still fails): {proposed}")
        accepted = trial
        last = result

    return HuntOutcome(status=last.status, invariants=accepted, iterations=max_iters, baseline=baseline, history=history)
