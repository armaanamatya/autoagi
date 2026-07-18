"""One-command Evo-style generation loop for the hunter prompt.

    python -m autoagi.evolve

Each generation:
  1. MUTATE  - Claude reads the current champion prompt + the failure ledger and
               proposes a full replacement prompt (the challenger).
  2. SCORE   - champion and challenger each run the hill-climb benchmark subset
               (evens, fifo, credits). Score = proofs_closed*100 - llm_iterations.
  3. PROMOTE - if the challenger strictly beats the champion, it becomes
               prompts/hunter.md (the old champion is archived, versioned).
  4. VERIFY  - a promoted challenger must also close the holdout set
               (token_ring, mult); otherwise the promotion is rolled back.

The optimizer never sees the holdout scores during mutation/scoring — holdout is
purely a post-promotion generalization gate, so the loop can't overfit its own
metric. All scoring is done by the sound verifier via the normal hunt loop.
"""

from __future__ import annotations

import os
import re
import shutil
import sys
from pathlib import Path

from . import llm
from .invariant_hunter import hunt
from .sby_runner import PROJECT_ROOT

PROMPTS = PROJECT_ROOT / "prompts"
CHAMPION = PROMPTS / "hunter.md"
LEDGER = PROJECT_ROOT / "results" / "ledger.tsv"
BENCH = PROJECT_ROOT / "benchmarks"

HILLCLIMB = ["evens", "fifo", "credits"]
HOLDOUT = ["token_ring", "mult"]
PLACEHOLDERS = ("{top}", "{design}", "{log}", "{history}")

MUTATE_PROMPT = """You are optimizing the prompt of an invariant-hunting agent for hardware formal
verification. The agent's prompt is given a design, a solver log, and history, and
must elicit strengthening invariants that close k-induction proofs in as few
iterations as possible.

Current champion prompt:
=== BEGIN CURRENT PROMPT ===
{current}
=== END CURRENT PROMPT ===

Recent experiment ledger (every row is a sound solver verdict; UNKNOWN trials and
screen-FAILs represent wasted iterations the new prompt should prevent):
```
{ledger}
```

Write ONE improved full replacement prompt. Hard requirements:
- Keep the literal placeholders {{top}}, {{design}}, {{log}}, {{history}} exactly once each.
- Keep the JSON-array-of-strings output contract.
- Any literal curly braces in example Verilog must be doubled ({{{{ }}}}) so the
  template still formats.
- Make targeted changes based on the ledger evidence; do not bloat the prompt.

Output ONLY the new prompt text between these exact markers:
=== BEGIN NEW PROMPT ===
<the full prompt>
=== END NEW PROMPT ===
"""


def score_prompt(prompt_path: Path, label: str) -> tuple[int, int, int]:
    """Run the hill-climb subset with the given prompt. Returns (score, closed, iters)."""
    os.environ["AUTOAGI_PROMPT"] = str(prompt_path)
    closed = iters = 0
    for top in HILLCLIMB:
        outcome = hunt(BENCH / f"{top}.sv", top, max_iters=3, log=lambda m: print(f"  [{label}] {m}"))
        closed += outcome.status == "PASS"
        iters += outcome.iterations
    score = closed * 100 - iters
    print(f"[{label}] closed={closed}/{len(HILLCLIMB)} iters={iters} score={score}")
    return score, closed, iters


def verify_holdout(prompt_path: Path) -> bool:
    os.environ["AUTOAGI_PROMPT"] = str(prompt_path)
    ok = True
    for top in HOLDOUT:
        outcome = hunt(BENCH / f"{top}.sv", top, max_iters=3, log=lambda m: print(f"  [holdout] {m}"))
        ok &= outcome.status == "PASS"
    return ok


def next_version() -> int:
    versions = [int(m.group(1)) for p in PROMPTS.glob("hunter_v*.md") if (m := re.match(r"hunter_v(\d+)", p.stem))]
    return max(versions, default=0) + 1


def mutate(current: str) -> str:
    ledger_tail = "\n".join(LEDGER.read_text(encoding="utf-8").splitlines()[-40:]) if LEDGER.exists() else "(empty)"
    reply = llm.ask(MUTATE_PROMPT.format(current=current, ledger=ledger_tail))
    m = re.search(r"=== BEGIN NEW PROMPT ===\s*(.*?)\s*=== END NEW PROMPT ===", reply, re.S)
    if not m:
        raise llm.LLMError("mutation reply had no prompt markers")
    return m.group(1) + "\n"


def valid_template(text: str) -> bool:
    try:
        if any(text.count(ph) != 1 for ph in PLACEHOLDERS):
            return False
        text.format(top="t", design="d", log="l", history="h")
        return True
    except (KeyError, ValueError, IndexError):
        return False


def repair_template(text: str) -> str:
    """Escape every literal brace, then restore the known placeholders.

    LLM-written prompts routinely contain literal Verilog braces
    (e.g. {AW{1'b0}}) that break str.format. This deterministic transform makes
    any text formattable while preserving the four required placeholders.
    """
    text = text.replace("{", "{{").replace("}", "}}")
    for ph in PLACEHOLDERS:
        text = text.replace("{" + ph + "}", ph)  # "{{top}}" -> "{top}"
    return text


def main() -> int:
    current = CHAMPION.read_text(encoding="utf-8")

    print("=== MUTATE: asking Claude for a challenger prompt ===")
    try:
        challenger_text = mutate(current)
    except llm.LLMError as e:
        print(f"mutation failed: {e}")
        return 1
    if not valid_template(challenger_text):
        repaired = repair_template(challenger_text)
        if valid_template(repaired):
            print("challenger auto-repaired (escaped literal braces)")
            challenger_text = repaired
        else:
            (PROMPTS / "hunter_challenger_rejected.md").write_text(challenger_text, encoding="utf-8")
            print("challenger REJECTED by checks: placeholders/format contract broken "
                  "(saved to prompts/hunter_challenger_rejected.md)")
            return 1
    challenger_path = PROMPTS / "hunter_challenger.md"
    challenger_path.write_text(challenger_text, encoding="utf-8")
    print(f"challenger written to {challenger_path} ({len(challenger_text)} chars)")

    print("\n=== SCORE: champion on hill-climb subset ===")
    champ_score, *_ = score_prompt(CHAMPION, "champion")
    print("\n=== SCORE: challenger on hill-climb subset ===")
    chal_score, *_ = score_prompt(challenger_path, "challenger")

    if chal_score <= champ_score:
        print(f"\nRESULT: champion retained ({champ_score} >= {chal_score}). Challenger kept for inspection.")
        return 0

    print(f"\nchallenger wins ({chal_score} > {champ_score}) - verifying on holdout before promotion...")
    if not verify_holdout(challenger_path):
        print("RESULT: challenger REJECTED - failed holdout generalization gate. Champion retained.")
        return 0

    version = next_version()
    archive = PROMPTS / f"hunter_v{version}.md"
    shutil.copy(challenger_path, archive)
    shutil.copy(challenger_path, CHAMPION)
    print(f"RESULT: challenger PROMOTED as {archive.name} and installed as hunter.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
