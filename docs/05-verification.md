# 5. Verification: bit-exact, not approximately right

[Contents](../README.md#contents) · previous: [Scenario F](scenarios/F.md) · next: [6. Results](06-results.md)

Every number in this repository that describes hardware comes from a model that the Verilog and the HLS C++
reproduce **word for word**. The chain has four links.

<p align="center"><img src="../figures/diagrams/verification.png" width="100%"></p>

1. **Floating point** ([`afarch/reference.py`](../afarch/reference.py)): the algorithms of the companion
   repository, re-implemented for the scenes of this one. They define what "right" means for an image.
2. **Bit-accurate models** ([`afarch/fxp.py`](../afarch/fxp.py), [`engines.py`](../afarch/engines.py),
   [`frontends.py`](../afarch/frontends.py), [`scenarios.py`](../afarch/scenarios.py)): integer arithmetic with
   the formats, rounding and saturation of [chapter 2](02-fixed-point.md), and one model per algorithmic class
   (exact, delayed, block). The pipelined classes are modelled **step by step**: an idle cycle is not a step, while
   a drain or pre-roll step is an empty step that still moves the pending updates. The models are what the
   experiments run on whole images.
3. **RTL** ([`rtl/`](../rtl)), simulated with Icarus Verilog against the models on the same inputs. The compile
   uses `-g2005 -Wall` (with the timescale and implicit-dimension notes off), and any warning fails the run.
4. **HLS C++** ([`hls/`](../hls)), compiled with g++ as a C simulation, once with 64-bit integers and once with the
   exact-width `ap_int<W>` types of Vitis HLS, against the same models.

Every output word must be equal: `np.array_equal`, no tolerance.

## 5.1 Engines

[`sim/test_engines.py`](../sim/test_engines.py) drives [`tb/tb_engine.v`](../tb/tb_engine.v) with a step file in
which every line is a step: valid sample, shift, drain, adapt flag, last-of-row flag, desired, pass-through and
taps. The streams are random and hostile on purpose:

* rows of random length (4 to 30 samples) ending with `last`, followed by drain bursts of random length, often
  shorter than the row-block commit needs (the model's commit delay then decides when the update lands);
* idle cycles inside rows (pipelined engines) and gaps between samples (handshake engines);
* random runs of pre-roll shifts in tapped-delay-line mode;
* full-scale taps (2 % of the samples), saturating desired values (1 %), outliers for the gated error unit (8 %)
  and adaptation switched off on 10 % of the samples.

24 cases cover the six engines with odd tap counts ($L=1$, 3, 5, 7, 13), the four update rules (LMS, sign-error,
sign-data, sign-sign), leakage, all four output modes, the gate, and both tap interfaces. A second run per
handshake engine feeds samples back to back and **measures the initiation interval**: 8 configurations, all equal
to the formulas of [chapter 1](01-foundations.md#15-six-engines-three-numbers) (`serial` $L=8$: 19, $L=24$: 51;
`folded` $L=24$, $P=1,4,6$: 29, 13, 12; $L=48$, $P=12$: 13; `da` $L=24$: 22, $L=128$: 24).

## 5.2 Scenario tops

[`sim/test_scenarios.py`](../sim/test_scenarios.py) runs the complete Verilog tops on image crops (a few hundred to
a few thousand pixels, several passes) through dedicated testbenches. 32 cases:

| group | cases | what is exercised |
|---|---|---|
| D, E | 10 | `window_gen` with reflection at all four borders, two planes, blind spots $H=0$ and $H=1$, every engine, the gated predictor over three passes with the tap plane taken from the previous pass |
| C | 6 | the two-phase row schedule, the Gaussian high band on signed codes, the V-ordered reflected history, pre-roll, every engine |
| A | 6 | phase accumulators across rows and frames, the cosine ROM, every engine |
| B | 3 | the three update modes, row starts |
| F | 5 | OB accumulation, dark-frame calibration then frozen correction, the leave-one-out online mode, the reference channel with $S=-1$, the tag FIFO |
| baselines | 2 | the $3\times3$ median and the switching median |

## 5.3 Smoke tests: every scenario, RTL and HLS

[`smoke/smoke.py`](../smoke/smoke.py) is the short test of the whole stack: 17 cases, two or three per scenario,
each a small crop with its configuration, run through the Verilog top and the HLS C++ top and compared with the
model ([`smoke/README.md`](../smoke/README.md), [`results/smoke.json`](../results/smoke.json)):

| scenario | cases | engines and modes |
|---|---|---|
| A | `A_serial`, `A_df` | exact and delayed, two plane waves, two passes |
| B | `B_lms`, `B_sign`, `B_gated` | the three update modes |
| C | `C_folded`, `C_df`, `C_rowblock` | exact, delayed and block, signed codes |
| D | `D_gated_serial`, `D_gated_df`, `D_systolic` | the gated predictor over three passes, the plain one |
| E | `E_systolic`, `E_rowblock`, `E_da` | $7\times7$ windows with blind spots $3\times3$ and $1\times1$ |
| F | `F_ob_cal`, `F_online`, `F_channel` | dark-frame calibration, online leave-one-out, reference channel |

All 17 pass on the RTL (with 10 % random idle cycles between pixels) and on the HLS C++ in both number modes. The
continuous integration runs them on every push, the `ap_int` mode with the open
[HLS arbitrary-precision headers](https://github.com/Xilinx/HLS_arbitrary_Precision_Types) fetched at test time.
With Vitis HLS installed, [`smoke/run_vitis.sh`](../smoke/run_vitis.sh) runs every case through C simulation,
C synthesis and C/RTL co-simulation and compares the co-simulation's output words with the model as well.

## 5.4 The application examples through both implementations

[`experiments/examples_hw.py`](../experiments/examples_hw.py) takes every configuration of the 18 application
examples ([6.1](06-results.md#61-application-examples)) through the HLS C++ top over the whole frame, and the
configurations marked for the RTL through the Verilog top: the whole frame for
A, B and F, a strip of 16 rows for C and a tile for D and E, where Icarus Verilog is slow (a few pixels per second
for the 128-tap direct form of C) ([`results/examples_hw.csv`](../results/examples_hw.csv)). The words compared are
those of the last pass or of the scene frame, which carry every earlier pass and calibration frame. Every one of
them equals the model's, so every PSNR quoted for an example is the PSNR of the Verilog and of the HLS C++ as
much as of the model.

These runs found one bug. In Verilog a concatenation makes a whole conditional expression unsigned, and the
Gaussian pre-adder of `scen_c_top`, `(gm == 0) ? {h[WD-1], h} : h_a + h_b`, therefore zero-extended its sum instead
of sign-extending it. The smoke and regression crops of C had non-negative codes; the C examples, whose stripes push
dark pixels below zero, did not. A `$signed()` on the concatenation fixes it, and the C cases of the smoke test and
the regression now use signed codes.

## 5.5 What the comparison guarantees, and what it does not

**Guaranteed.** For the tested configurations, the RTL and the HLS C++ compute exactly what the model computes,
including saturation, rounding, row boundaries, drains and idle cycles. Because two's complement addition is
associative, the engines of one class produce identical images ([1.5](01-foundations.md#15-six-engines-three-numbers));
the experiments therefore report one result per class plus the delay of each engine.

**Not covered by simulation here.** Timing closure on a device (the repository reports Yosys cell counts, not clock
frequencies), the schedule that Vitis HLS chooses (the initiation intervals and resources of the HLS tops are
targets, in red, until [`hls/scripts/run_vitis_hls.tcl`](../hls/scripts/run_vitis_hls.tcl) has been run), the
behaviour of a real sensor interface, and parameter values far outside the tested ones (the models assert the
word-growth conditions of [2.4](02-fixed-point.md#24-word-growth-and-guard-bits) on every sample, and the HLS
`narrow<W>()` asserts the same in 64-bit C simulation, so an overflow stops a run instead of passing silently). The
A4 lattice notch is a floating-point model only.

## 5.6 Running it

```bash
python sim/test_engines.py                 # 24 engine cases + 8 initiation intervals, a few seconds
python sim/test_scenarios.py               # 32 scenario cases, about a minute
python smoke/smoke.py                      # 17 smoke cases, RTL and HLS, about 2 minutes
python smoke/smoke.py --only hls --ap-types <dir with ap_int.h>
python experiments/examples_hw.py --no-rtl # the 18 examples through the HLS tops, a few minutes
python experiments/examples_hw.py          # and through the Verilog tops, about an hour
```

The scripts need `iverilog` and `vvp` (RTL) and `g++` (HLS) on the path; when run in full they write
`results/rtl_engine_tests.json`, `results/rtl_scenario_tests.json`, `results/smoke.json` and
`results/examples_hw.csv`. The first three commands run in the continuous integration of the repository
([`.github/workflows/ci.yml`](../.github/workflows/ci.yml)).
