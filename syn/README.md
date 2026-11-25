# syn/: synthesis

[Repository](../README.md) · [RTL](../rtl/README.md) · [results](../docs/06-results.md#64-synthesis)

| script | what it does | output |
|---|---|---|
| [`synth_engines.py`](synth_engines.py) | every engine through Yosys `synth_xilinx -family xc7` for several tap counts and lane counts; `--smoke` runs one small configuration per engine and fails on an empty netlist (the CI job) | [`results/synth_engines.csv`](../results/synth_engines.csv) |
| [`synth_tops.py`](synth_tops.py) | the scenario tops at $W=512$ with their engines; `python syn/synth_tops.py C D` for some | [`results/synth_tops.csv`](../results/synth_tops.csv) |
| [`vivado_ooc.tcl`](vivado_ooc.tcl) | any module through Vivado out of context: synthesis, placement, routing, utilisation and timing reports in `build/vivado/` | (no result reported here) |

```bash
python syn/synth_engines.py
python syn/synth_tops.py
vivado -mode batch -source syn/vivado_ooc.tcl -tclargs lms_engine xc7a200tsbg484-1 4.0 ENGINE=2 L=24
```

The counts are cells after `synth_xilinx`: DSP48E1, LUT, FF, SRL, LUTRAM, RAMB18/36, CARRY4, MUXF. The parser
([`afarch/synth.py`](../afarch/synth.py)) reads the `stat` output of both the older (0.3x) and the newer Yosys
formats; the results in this repository come from Yosys 0.71. Yosys runs from `rtl/scenarios` so that `scen_a_top`
finds its cosine table. For HLS synthesis see [`hls/scripts/run_vitis_hls.tcl`](../hls/scripts/run_vitis_hls.tcl).
