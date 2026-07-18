"""LLM backend for candidate generation.

Two backends, picked automatically:
  1. anthropic SDK  - used when ANTHROPIC_API_KEY is set and the package is installed.
  2. claude CLI     - default; shells out to `claude -p`, which reuses the local
                      Claude Code login (no API key required).

Either way the LLM is untrusted: its output is parsed as a JSON list of candidate
invariant expressions and every candidate is checked by SymbiYosys before it counts.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess

DEFAULT_CLI_MODEL = os.environ.get("AUTOAGI_MODEL", "opus")
SDK_MODEL = "claude-opus-4-8"


class LLMError(RuntimeError):
    pass


def _ask_sdk(prompt: str) -> str:
    import anthropic

    client = anthropic.Anthropic()
    response = client.messages.create(
        model=SDK_MODEL,
        max_tokens=16000,
        thinking={"type": "adaptive"},
        messages=[{"role": "user", "content": prompt}],
    )
    return "".join(block.text for block in response.content if block.type == "text")


def _ask_cli(prompt: str) -> str:
    exe = shutil.which("claude")
    if exe is None:
        raise LLMError("claude CLI not found on PATH and no ANTHROPIC_API_KEY set")
    proc = subprocess.run(
        [exe, "-p", "--output-format", "text", "--model", DEFAULT_CLI_MODEL],
        input=prompt,
        capture_output=True,
        text=True,
        timeout=600,
        encoding="utf-8",
        errors="replace",
    )
    if proc.returncode != 0:
        raise LLMError(f"claude CLI failed (rc={proc.returncode}): {proc.stderr[-2000:]}")
    return proc.stdout


def _ask_pi(prompt: str) -> str:
    """Pi coding-agent harness backend (`pi -p`), for Introspection recipe runs."""
    exe = shutil.which("pi")
    if exe is None:
        raise LLMError("pi CLI not found on PATH (AUTOAGI_BACKEND=pi)")
    proc = subprocess.run(
        [exe, "-p", prompt],
        capture_output=True,
        text=True,
        timeout=600,
        encoding="utf-8",
        errors="replace",
    )
    if proc.returncode != 0:
        raise LLMError(f"pi CLI failed (rc={proc.returncode}): {proc.stderr[-2000:]}")
    return proc.stdout


def ask(prompt: str) -> str:
    backend = os.environ.get("AUTOAGI_BACKEND", "").lower()
    if backend == "pi":
        return _ask_pi(prompt)
    if backend == "sdk" or (not backend and os.environ.get("ANTHROPIC_API_KEY")):
        try:
            import anthropic  # noqa: F401

            return _ask_sdk(prompt)
        except ImportError:
            pass
    return _ask_cli(prompt)


def extract_json_list(text: str) -> list[str]:
    """Pull the first JSON array of strings out of an LLM response.

    Uses raw_decode at every '[' so expressions containing brackets
    (e.g. "cnt[0] == 1'b0") parse correctly.
    """
    decoder = json.JSONDecoder()
    fence = re.search(r"```(?:json)?\s*(.*?)```", text, re.S)
    sources = ([fence.group(1)] if fence else []) + [text]
    for src in sources:
        for m in re.finditer(r"\[", src):
            try:
                data, _ = decoder.raw_decode(src, m.start())
            except json.JSONDecodeError:
                continue
            if isinstance(data, list) and data and all(isinstance(x, str) for x in data):
                return data
    raise LLMError(f"no JSON string-array found in LLM response:\n{text[-1500:]}")
