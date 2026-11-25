#!/usr/bin/env bash
# The smoke cases through Vitis HLS: C simulation with the ap_int headers of the installed Vitis, then for every
# case C synthesis and C/RTL co-simulation (hls/scripts/run_vitis_hls.tcl), then the word-for-word comparison of
# the co-simulation outputs with the golden outputs.
#
#   source <Vitis install>/settings64.sh
#   bash smoke/run_vitis.sh                 # every scenario
#   bash smoke/run_vitis.sh D E             # some scenarios
#   FLOW=syn bash smoke/run_vitis.sh C      # C simulation and synthesis only (csim | syn | cosim | export)
#   PART=xczu7ev-ffvc1156-2-e PERIOD=3.0 bash smoke/run_vitis.sh D
set -euo pipefail
cd "$(dirname "$0")/.."
: "${XILINX_HLS:?source the settings64.sh of the Vitis installation first}"
FLOW=${FLOW:-cosim}
PART=${PART:-xc7a200tsbg484-1}
PERIOD=${PERIOD:-4.0}
SCEN=("$@")
[ ${#SCEN[@]} -eq 0 ] && SCEN=(A B C D E F)

python smoke/smoke.py --only hls --ap-types "$XILINX_HLS/include" "${SCEN[@]}"
for c in $(python smoke/smoke.py --list "${SCEN[@]}"); do
    printf '\n== %s (%s)\n' "$c" "$FLOW"
    if command -v vitis_hls >/dev/null 2>&1; then
        vitis_hls -f hls/scripts/run_vitis_hls.tcl -tclargs "$c" "$FLOW" "$PART" "$PERIOD"
    else
        AF_CASE=$c AF_FLOW=$FLOW AF_PART=$PART AF_PERIOD=$PERIOD vitis-run --mode hls --tcl hls/scripts/run_vitis_hls.tcl
    fi
done
python smoke/smoke.py --vitis "${SCEN[@]}"
