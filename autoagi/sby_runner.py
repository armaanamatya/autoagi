"""Run SymbiYosys (sby) k-induction jobs and parse the verdict.

The verdict model:
  PASS    - base case and induction both hold: property proved.
  FAIL    - base case fails: a real counterexample (or a false candidate invariant).
  UNKNOWN - base case holds but induction fails: property likely true but not
            inductive; this is the signal that strengthening invariants are needed.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
RESULTS_DIR = PROJECT_ROOT / "results"
TOOLS_DIR = PROJECT_ROOT / "tools"

INVARIANT_MARKER = "// %INVARIANTS%"


def _find_env_script() -> Path | None:
    """Locate the OSS CAD Suite environment script (Windows: environment.bat)."""
    for cand in (
        TOOLS_DIR / "oss-cad-suite" / "environment.bat",
        TOOLS_DIR / "environment.bat",
    ):
        if cand.exists():
            return cand
    return None


def _find_suite_bin() -> Path | None:
    for cand in (TOOLS_DIR / "oss-cad-suite" / "bin", TOOLS_DIR / "bin"):
        if cand.exists():
            return cand
    return None


def sby_available() -> bool:
    import shutil

    return shutil.which("sby") is not None or _find_env_script() is not None


@dataclass
class SbyResult:
    status: str  # "PASS" | "FAIL" | "UNKNOWN" | "ERROR"
    returncode: int
    elapsed_s: float
    log: str
    workdir: Path

    @property
    def induction_failed(self) -> bool:
        return self.status == "UNKNOWN"


def make_sby_job(design_text: str, top: str, workdir: Path, depth: int = 10, engine: str = "smtbmc") -> Path:
    """Write the design and a .sby file into workdir; return the .sby path."""
    workdir.mkdir(parents=True, exist_ok=True)
    src = workdir / f"{top}.sv"
    src.write_text(design_text, encoding="utf-8")

    sby = workdir / f"{top}.sby"
    sby.write_text(
        "\n".join(
            [
                "[options]",
                "mode prove",
                f"depth {depth}",
                "",
                "[engines]",
                engine,
                "",
                "[script]",
                f"read -formal -DFORMAL {top}.sv",
                f"prep -top {top}",
                "",
                "[files]",
                f"{top}.sv",
                "",
            ]
        ),
        encoding="utf-8",
    )
    return sby


def run_sby(sby_file: Path, timeout_s: int = 300) -> SbyResult:
    """Run sby on the given job file and classify the outcome.

    Output goes to a log file rather than a pipe: on Windows, sby's solver
    children inherit pipe handles, which makes pipe-based timeouts hang forever.
    On timeout the whole process tree is killed and status is TIMEOUT.
    """
    env_script = _find_env_script()
    start = time.monotonic()
    logpath = sby_file.parent / f"{sby_file.stem}_run.log"
    timed_out = False

    with logpath.open("w", encoding="utf-8", errors="replace") as out:
        if os.name == "nt" and env_script is not None:
            proc = subprocess.Popen(
                f'call "{env_script}" && sby -f "{sby_file.name}"',
                shell=True,
                cwd=sby_file.parent,
                stdout=out,
                stderr=subprocess.STDOUT,
            )
        else:
            env = os.environ.copy()
            suite_bin = _find_suite_bin()
            if suite_bin is not None:
                env["PATH"] = str(suite_bin) + os.pathsep + env.get("PATH", "")
            proc = subprocess.Popen(
                ["sby", "-f", sby_file.name],
                cwd=sby_file.parent,
                stdout=out,
                stderr=subprocess.STDOUT,
                env=env,
            )
        try:
            proc.wait(timeout=timeout_s)
        except subprocess.TimeoutExpired:
            timed_out = True
            if os.name == "nt":
                subprocess.run(
                    ["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                    capture_output=True,
                )
            else:
                proc.kill()
            proc.wait()

    elapsed = time.monotonic() - start
    log = logpath.read_text(encoding="utf-8", errors="replace")

    if re.search(r"DONE \(PASS", log):
        status = "PASS"
    elif re.search(r"DONE \(FAIL", log):
        status = "FAIL"
    elif re.search(r"DONE \(UNKNOWN", log):
        status = "UNKNOWN"
    elif timed_out:
        status = "TIMEOUT"
    else:
        status = "ERROR"

    # sby's own work directory sits next to the .sby file, named after the job
    workdir = sby_file.parent / sby_file.stem
    return SbyResult(status=status, returncode=proc.returncode or 0, elapsed_s=elapsed, log=log, workdir=workdir)


def prove(design_text: str, top: str, label: str = "job", depth: int = 10, timeout_s: int = 300, engine: str = "smtbmc") -> SbyResult:
    """One-shot: write a job for design_text and run it."""
    job_dir = RESULTS_DIR / f"{top}_{label}"
    sby_file = make_sby_job(design_text, top, job_dir, depth=depth, engine=engine)
    return run_sby(sby_file, timeout_s=timeout_s)


def inject_invariants(design_text: str, invariants: list[str]) -> str:
    """Insert candidate invariant statements at the %INVARIANTS% marker."""
    if INVARIANT_MARKER not in design_text:
        raise ValueError(f"design has no '{INVARIANT_MARKER}' marker")
    if not invariants:
        return design_text
    block = "\n".join(
        [INVARIANT_MARKER, "    // candidate strengthening invariants (LLM-proposed, solver-checked)"]
        + [f"    always @(posedge clk) if (f_past_valid) assert ({inv});" for inv in invariants]
    )
    return design_text.replace(INVARIANT_MARKER, block)


def inject_covers(design_text: str, covers: list[str]) -> str:
    """Insert named cover points at the %INVARIANTS% marker (vacuity checks:
    a proof that never covers an interesting state may be trivially true)."""
    if INVARIANT_MARKER not in design_text:
        raise ValueError(f"design has no '{INVARIANT_MARKER}' marker")
    block = "\n".join(
        [INVARIANT_MARKER, "    // reachability witnesses (vacuity check, not a proof obligation)"]
        + [f"    always @(posedge clk) if (f_past_valid) cover ({c});" for c in covers]
    )
    return design_text.replace(INVARIANT_MARKER, block)


def inject_invariants_and_covers(design_text: str, invariants: list[str], covers: list[str]) -> str:
    """Both `inject_invariants` and `inject_covers` replace the single
    %INVARIANTS% marker, so checking vacuity of an *accepted* proof (its
    invariants held as constraints, cover points as the reachability probe)
    needs them combined into one substitution."""
    if INVARIANT_MARKER not in design_text:
        raise ValueError(f"design has no '{INVARIANT_MARKER}' marker")
    lines = [INVARIANT_MARKER]
    if invariants:
        lines.append("    // accepted strengthening invariants (solver-checked)")
        lines += [f"    always @(posedge clk) if (f_past_valid) assert ({inv});" for inv in invariants]
    if covers:
        lines.append("    // reachability witnesses (vacuity check, not a proof obligation)")
        lines += [f"    always @(posedge clk) if (f_past_valid) cover ({c});" for c in covers]
    return design_text.replace(INVARIANT_MARKER, "\n".join(lines))


def make_cover_job(design_text: str, top: str, workdir: Path, depth: int = 20, engine: str = "smtbmc") -> Path:
    """Like make_sby_job but `mode cover`: find a witness trace reaching each
    cover() point instead of proving assertions hold everywhere."""
    workdir.mkdir(parents=True, exist_ok=True)
    src = workdir / f"{top}.sv"
    src.write_text(design_text, encoding="utf-8")

    sby = workdir / f"{top}.sby"
    sby.write_text(
        "\n".join(
            [
                "[options]",
                "mode cover",
                f"depth {depth}",
                "",
                "[engines]",
                engine,
                "",
                "[script]",
                f"read -formal -DFORMAL {top}.sv",
                f"prep -top {top}",
                "",
                "[files]",
                f"{top}.sv",
                "",
            ]
        ),
        encoding="utf-8",
    )
    return sby


_COVER_REACHED_RE = re.compile(r"Reached cover statement .*?\b(\d+)\.\d+-\d+\.\d+\b.*?in step (\d+)")
_COVER_LINE_RE = re.compile(r"Reached cover statement.*?:(\d+)\.")


def check_vacuity(base_design_text: str, top: str, covers: list[str], invariants: list[str] | None = None,
                   depth: int = 20, timeout_s: int = 300, engine: str = "smtbmc") -> dict[str, object]:
    """Run mode-cover on base_design_text + accepted invariants (held as
    constraints, same as the real proof) + named cover() points, and report
    per cover expression whether a solver found a reachable witness. A
    'PASS' proof whose interesting states are all unreached is vacuous."""
    design = inject_invariants_and_covers(base_design_text, invariants or [], covers)
    job_dir = RESULTS_DIR / f"{top}_vacuity"
    sby_file = make_cover_job(design, top, job_dir, depth=depth, engine=engine)
    result = run_sby(sby_file, timeout_s=timeout_s)

    # Map injected cover() lines back to which expression they belong to.
    lines = design.splitlines()
    cover_line_of: dict[int, str] = {}
    ci = 0
    for i, ln in enumerate(lines, start=1):
        if "cover (" in ln and ci < len(covers):
            cover_line_of[i] = covers[ci]
            ci += 1

    reached_lines = {int(m) for m in _COVER_LINE_RE.findall(result.log)}
    reached = {expr: (lineno in reached_lines) for lineno, expr in cover_line_of.items()}
    return {"status": result.status, "reached": reached, "log_tail": summarize_log(result.log), "elapsed_s": result.elapsed_s}


_ASSERT_LOC_RE = re.compile(r"Assert failed in \w+: \S+?\.sv:(\d+)")


def failing_assert_line(result: SbyResult, top: str) -> str | None:
    """Return the source text of the assert that failed (last failure in the log)."""
    matches = _ASSERT_LOC_RE.findall(result.log)
    if not matches:
        return None
    lineno = int(matches[-1])
    src = result.workdir.parent / f"{top}.sv"
    try:
        lines = src.read_text(encoding="utf-8").splitlines()
        return lines[lineno - 1].strip()
    except (OSError, IndexError):
        return None


def summarize_log(log: str, max_chars: int = 4000) -> str:
    """Trim an sby log to the interesting tail (induction/basecase lines and errors)."""
    lines = [
        ln
        for ln in log.splitlines()
        if re.search(r"(induction|basecase|Assert failed|Unreached|ERROR|Status|DONE|Trace)", ln, re.I)
    ]
    text = "\n".join(lines) if lines else log
    return text[-max_chars:]
