# afarch/: the models of the hardware

[Repository](../README.md) · [RTL](../rtl/README.md) · [HLS C++](../hls/README.md) · [verification](../docs/05-verification.md)

The Python package that both implementations are checked against. The floating-point algorithms define what a
good image is; the bit-accurate models define what the hardware computes, sample by sample, and every experiment
runs on them.

| module | contents |
|---|---|
| [`fxp.py`](fxp.py) | `Arith`: the arithmetic contract ([chapter 2](../docs/02-fixed-point.md)): Q12 codes, the 48-bit weight accumulator and its view, rounding, saturation, the four update rules, leakage; `step_exponent()` |
| [`engines.py`](engines.py) | `Engine`: step-accurate models of the three classes (exact, delayed with delay $D$, block with commit delay $D_c$); `ErrUnit` and `Gate`; the delays of the six engines |
| [`frontends.py`](frontends.py) | reflected windows and blind spots, the Gaussian high band and the tapped delay line of C, the plane-wave references of A, the OB mean of F |
| [`scenarios.py`](scenarios.py) | `scenario_a`, `scenario_a_log`, `scenario_b`, `scenario_c`, `scenario_de`, `scenario_f_row`, `scenario_f_online`, `scenario_f_channel`, `median3x3`: the fixed-point pipelines of the tops, pre-roll and drains included |
| [`reference.py`](reference.py) | the floating-point algorithms of the companion repository, PSNR, SSIM, image loading |
| [`scenes.py`](scenes.py) | the corrupted scenes of the examples, with fixed seeds |
| [`lattice.py`](lattice.py) | architecture A4, the adaptive lattice notch (floating point) |
| [`cost.py`](cost.py) | time and area formulas, the DLMS bound, the worst-row eigenvalue and the block step |
| [`hdl.py`](hdl.py) | Icarus Verilog driver (compile with `-g2005 -Wall`, fail on warnings, run) |
| [`hwrun.py`](hwrun.py) | any scenario input through the Verilog top (`impl="rtl"`) or the HLS C++ top (`impl="hls"`, int64 or `ap_int`), or the output of a Vitis HLS run (`impl="vitis"`) |
| [`synth.py`](synth.py) | Yosys driver and `stat` parser |
| [`plotstyle.py`](plotstyle.py) | colours, fonts and the block-diagram canvas of the figures |

```python
from afarch import scenarios as sc, hwrun
from afarch.fxp import Arith

ar = Arith(S=8)
codes = ar.code(noisy)                                             # Q12 codes
model = ar.code(sc.scenario_de(noisy, S=8, R=2, passes=2, engine="df"))
hls = hwrun.scen_de("build/x", codes, R=2, HOLE=0, S=8, engine="df", passes=2, gated=False,
                    off=int(ar.code(noisy.mean())), impl="hls")    # every pass, (pixel, flag) per word
assert (hls[-codes.size:, 0] == model.ravel()).all()
```
