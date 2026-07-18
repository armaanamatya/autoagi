# autoagi — 3-minute live demo
# Run from the repo root. Each step pauses for you to talk.

function Pause-Step($msg) { Write-Host "`n>>> $msg" -ForegroundColor Cyan; Read-Host "  [enter to run]" | Out-Null }

Pause-Step "1/4  The solver alone gets stuck: multiplier property is TRUE but not inductive"
python -m autoagi.cli prove benchmarks\mult.sv

Pause-Step "2/4  The loop: Claude reads the design, proposes the algorithmic loop invariant, solver proves it"
python -m autoagi.cli hunt benchmarks\mult.sv

Pause-Step "3/4  The receipts: every solver verdict, timestamped (note the fifo eviction rows)"
Get-Content results\ledger.tsv | Select-Object -Last 20

Pause-Step "4/5  The improvement loop: mutate prompt -> score vs champion -> holdout gate -> promote"
python -m autoagi.evolve

Pause-Step "5/5  Second sound checker: the fifo eviction, kernel-checked in Lean 4"
& "$env:USERPROFILE\.elan\bin\lean.exe" lean\FifoEviction.lean
