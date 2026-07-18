#!/usr/bin/env bash
# pi-evo-research correctness backpressure: a mutated prompt must keep the
# format placeholders the harness injects, and must still parse as a template.
set -euo pipefail
cd "$(dirname "$0")"

python - <<'EOF'
from pathlib import Path

text = Path("prompts/hunter.md").read_text(encoding="utf-8")
for key in ("{top}", "{design}", "{log}", "{history}"):
    assert key in text, f"prompt mutation broke required placeholder {key}"
# formatting must not raise (catches stray unescaped braces)
text.format(top="t", design="d", log="l", history="h")
print("CHECK ok: prompt placeholders intact and formattable")
EOF
