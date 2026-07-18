#!/usr/bin/env bash
# pi-evo-research benchmark script.
#
# The evolvable artifact is prompts/hunter.md (the invariant-hunter prompt).
# The population mutates that file; this script scores the current version by
# running the hill-climb benchmark set and emitting METRIC lines. The holdout
# set (token_ring, mult) is NEVER run here — it is reserved for generalization
# checks on promoted candidates, so the loop can't overfit the prompt to the
# scored benchmarks.
set -euo pipefail
cd "$(dirname "$0")"

python -u -m autoagi.cli bench --set hillclimb --iters 3 --metrics
