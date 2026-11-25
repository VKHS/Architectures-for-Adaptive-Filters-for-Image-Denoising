#!/usr/bin/env bash
# Regenerate every result and figure of the repository, in dependency order.
#
#   bash scripts/run_all.sh            # everything (tests, synthesis, experiments, figures)
#   bash scripts/run_all.sh --no-syn   # skip the Yosys runs (keeps results/synth_*.csv)
#
# Needs Python with requirements.txt, Icarus Verilog (iverilog, vvp), g++ and, for synthesis, Yosys on the PATH.
# The examples through the Verilog tops (experiments/examples_hw.py without --no-rtl) take about an hour and are
# not part of this script.
set -euo pipefail
cd "$(dirname "$0")/.."

step() { printf '\n== %s\n' "$*"; }

step "RTL against the models"
python sim/test_engines.py
python sim/test_scenarios.py

step "Smoke tests: every scenario, RTL and HLS C++"
python smoke/smoke.py

if [[ "${1:-}" != "--no-syn" ]]; then
    step "Yosys synthesis (results/synth_engines.csv, results/synth_tops.csv)"
    python syn/synth_engines.py
    python syn/synth_tops.py
fi

step "Experiments"
python experiments/delay_sweep.py          # DLMS against the delay (figures/results/delay_sweep.png)
python experiments/rowblock_wordlength.py  # block LMS against the step, weight word length
python experiments/examples.py             # the 18 application examples
python experiments/examples_hw.py --no-rtl # the examples through the HLS C++ tops, word for word
python experiments/algorithms.py           # the algorithm figures of the six scenarios
python experiments/design_space.py         # cycles per pixel against multipliers (reads the synthesis csv)

step "Block diagrams"
python experiments/diagrams.py
