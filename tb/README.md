# tb/: the Verilog testbenches

[Repository](../README.md) · [RTL](../rtl/README.md) · [regressions](../sim/README.md) · [smoke tests](../smoke/README.md)

The testbenches replay stimulus files written by the Python drivers and log every output; the drivers compare the
log with the bit-accurate model ([`afarch`](../afarch/README.md)). None of them checks anything itself: the
comparison, word for word, is always against the model.

| testbench | drives | stimulus | log | driven by |
|---|---|---|---|---|
| [`tb_engine.v`](tb_engine.v) | `lms_engine`, any `ENGINE` | step file: `valid shift drain adapt last d p x` per line (taps in hex) | `I <cycle>` per accepted sample, `O <cycle> o y e flag` per output | [`sim/test_engines.py`](../sim/test_engines.py) |
| [`tb_scen_a.v`](tb_scen_a.v) | `scen_a_top` | an image in hex, streamed `PASSES` times | `O pix 0` | [`sim/test_scenarios.py`](../sim/test_scenarios.py), [`afarch/hwrun.py`](../afarch/hwrun.py) |
| [`tb_scen_c.v`](tb_scen_c.v) | `scen_c_top` | an image in hex | `O pix 0` | the same |
| [`tb_scen_de.v`](tb_scen_de.v) | `scen_de_top` | an image in hex, `PASSES` passes; gated: the tap plane of a later pass is the previous output | `O pix flag` | the same |
| [`tb_scen_bf.v`](tb_scen_bf.v) | `scen_b_top` (`TOP = 0`) or `scen_f_top` (`TOP = 1`) | step file: `mode flush pix ref` per line; `flush = 1` ends a frame | `O pix bias` | the same |
| [`tb_median.v`](tb_median.v) | `median3x3_top` | an image in hex | `O pix flag` | [`sim/test_scenarios.py`](../sim/test_scenarios.py) |

Every testbench inserts random idle cycles between pixels (`IDLE_PROB`, in percent; 10 in the regressions and the
smoke tests, 0 for the long example runs): the tops must not care when the data arrive. Parameters are passed by
the drivers with `iverilog -P`; [`afarch/hdl.py`](../afarch/hdl.py) compiles with `-g2005 -Wall` and fails on any
warning.

The HLS C++ tops have their own C-simulation testbenches in [`hls/tb`](../hls/tb), with the same inputs and the
same output words.
