# Architectures for Adaptive Filters for Image Denoising

[![RTL verification](https://github.com/VKHS/Architectures-for-Adaptive-Filters-for-Image-Denoising/actions/workflows/ci.yml/badge.svg)](https://github.com/VKHS/Architectures-for-Adaptive-Filters-for-Image-Denoising/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![ORCID](https://img.shields.io/badge/ORCID-0000--0003--4870--2768-A6CE39?logo=orcid&logoColor=white)](https://orcid.org/0000-0003-4870-2768)

**Abdolvahab Khalili Sadaghiani** · ORCID [0000-0003-4870-2768](https://orcid.org/0000-0003-4870-2768) ·
Department of Electrical Engineering, Linköping University

The FPGA counterpart of [Adaptive Filters for Image Denoising](https://github.com/VKHS/Adaptive-Filters-for-Image-Denoising).
That repository explains the six LMS denoising scenarios as algorithms; this one explains how to build them:
why the LMS loop limits the clock, the three ways around that limit and the six engines that implement them, one
fixed-point arithmetic for all of them, the streaming front ends that turn a raster into taps, and **25
architectures** for the six scenarios. Every engine and every scenario top is Verilog, and every one reproduces a
bit-accurate model **word for word**; every resource figure is a Yosys count; every image result is computed on
the models of the RTL.

<p align="center"><img src="figures/diagrams/architecture_map.png" width="100%"></p>

## Contents

| | chapter | what it answers |
|---|---|---|
| 1 | [From the LMS loop to an architecture](docs/01-foundations.md) | the iteration bound; folding; delayed LMS and its exact stability bound; block LMS and its bound; why images need the worst tile and the worst row |
| 2 | [Fixed point](docs/02-fixed-point.md) | Q12 data, Q20 weights, the 48-bit weight accumulator that makes $\mu=2^{-S}$ a bit position and never stalls |
| 3 | [The six engines](docs/03-engines.md) | `lms_serial`, `lms_folded`, `lms_df`, `lms_systolic`, `lms_rowblock`, `lms_da` and the shared error unit, with block diagrams and costs |
| 4 | [Front ends](docs/04-front-ends.md) | the window generator with reflected borders, C's high band and reflected history, plane waves from phase accumulators, optical-black references |
| A–F | [A](docs/scenarios/A.md) · [B](docs/scenarios/B.md) · [C](docs/scenarios/C.md) · [D](docs/scenarios/D.md) · [E](docs/scenarios/E.md) · [F](docs/scenarios/F.md) | each scenario: algorithm, architectures, derivations, measurements, example |
| 5 | [Verification](docs/05-verification.md) | how the RTL is checked against the models, and what that does and does not cover |
| 6 | [Results](docs/06-results.md) | application examples, row-block LMS, design space, synthesis |
| 7 | [Choosing an architecture](docs/07-choosing.md) | a procedure, the scenarios at three video formats, a worked example |
| | [References](docs/references.md) | with DOIs; BibTeX in [`references.bib`](references.bib) |

## The argument in nine results

1. **The loop sets the clock.** The LMS recursion closes a loop through two multiplications, an adder tree, the
   error subtraction and the update addition, with one register:
   $T_\infty=2T_\times+(\lceil\log_2L\rceil+2)T_+$. Retiming cannot change it. There are three ways around it:
   **fold** (exact LMS, several cycles per pixel), **delay** (DLMS, one pixel per cycle) and **block** (one update
   per row). The six engines are the practical forms of these three ([1.1](docs/01-foundations.md#11-the-loop)).
2. **Exact LMS cannot reach one pixel per clock.** Folded over $P$ lanes it needs
   $\lceil L/P\rceil+\lceil\log_2P\rceil+5$ cycles, which floors at $\lceil\log_2L\rceil+6$: 11 cycles for 24 taps,
   however many multipliers are spent ([1.2](docs/01-foundations.md#12-folding-exact-lms-at-ii--1),
   [6.3](docs/06-results.md#63-design-space)).
3. **The DLMS bound is exact, and images need its local form.** $0<\mu\lambda<2\sin\frac{\pi}{2(2D+1)}$, derived
   from the roots of $z^{D}(z-1)=-\mu\lambda$. With the eigenvalue of the worst $64\times64$ tile it predicts where
   the fixed-point predictor diverges (between $D=64$ and $D=128$); with the image-wide eigenvalue it would not
   ([1.3](docs/01-foundations.md#13-delaying-the-update-dlms)).
4. **A systolic array is a DLMS with one delay for every tap.** In skewed weights $\hat w_j(m)=w_j(m+j)$ the
   systolic LMS is an ordinary DLMS with $D=L+3$, so its margin shrinks as $1/L$; at the delays the engines
   actually have, DLMS costs at most 0.15 dB.
5. **Block LMS needs $\mu N\lambda_{\max,\text{row}}<2$ with the worst row.** The condition separates divergence from
   convergence exactly in both tested scenes; inside it, the row-block engines match exact LMS to within 0.07 dB
   ([6.2](docs/06-results.md#62-row-block-lms)).
6. **One weight accumulator removes stalling.** Keeping $A=w\cdot2^{V}$ with the step as a bit position keeps
   every update; a 20-bit weight register would lose 0.11 dB on the LED-flicker example ($\mu=2^{-17}$), an 18-bit
   one 0.85 dB. Over the six examples, fixed point costs at most 0.06 dB
   ([2.3](docs/02-fixed-point.md#23-stalling-in-a-weight-register)).
7. **Borders cost nothing.** Reading the row buffers at reflected addresses produces the software's reflect-padded
   windows with no padded storage and no multiplexers on the window
   ([4.1](docs/04-front-ends.md#41-borders-without-padding-reflected-addressing)).
8. **A frequency can be one coefficient.** A lattice IIR notch (architecture A4) tracks stripes whose frequency
   drifts from 0.08 to 0.12 cycles/pixel with 5 multipliers: 32.66 dB, against 32.48 dB for the 128-tap canceller
   of C ([A](docs/scenarios/A.md#a4-an-iir-notch-that-finds-the-frequency-itself)).
9. **Verified bit for bit, counted by Yosys.** 24 engine cases, 8 measured initiation intervals and 32
   scenario-top cases pass with every output word equal; every multiplier maps onto one DSP48E1
   ([5](docs/05-verification.md), [6.4](docs/06-results.md#64-synthesis)).

## The loop, and the three ways around it

<p align="center"><img src="figures/diagrams/lms_loop.png" width="100%"></p>

| | engine | class | multipliers | cycles per pixel $II$ | adaptation delay $D$ | at $L=24$ (Yosys, xc7) |
|---|---|---|---|---|---|---|
| fold | [`lms_serial`](docs/03-engines.md#31-lms_serial) | exact LMS | 1 | $2L+3$ | 0 | 1 DSP, 475 LUT |
| fold | [`lms_folded`](docs/03-engines.md#32-lms_folded) | exact LMS | $2P$ | $\lceil L/P\rceil+\lceil\log_2P\rceil+5$ | 0 | $P=6$: 12 DSP, 1295 LUT |
| delay | [`lms_df`](docs/03-engines.md#33-lms_df) | delayed LMS | $2L$ | 1 | $\lceil\log_2L\rceil+3$ | 48 DSP, 1551 LUT |
| delay | [`lms_systolic`](docs/03-engines.md#34-lms_systolic) | delayed LMS | $2L$ | 1 | $L+3$ | 48 DSP, 1077 LUT |
| block | [`lms_rowblock`](docs/03-engines.md#35-lms_rowblock) | block LMS | $2L$ | 1 | one row | 48 DSP, 5032 LUT |
| block | [`lms_da`](docs/03-engines.md#36-lms_da) | block LMS | 0 | $W_D+\lceil\log_2\lceil L/4\rceil\rceil+3$ | one row | 0 DSP, 6985 LUT |

All six share one port list ([`lms_engine.v`](rtl/engines/lms_engine.v), `ENGINE = 0..5`), one arithmetic and one
error unit, so any scenario top runs on any engine. Within a class the engines are bit-identical, because two's
complement addition is associative: the order in which they add the same products cannot change the result.

## The six scenarios

| | scenario | reference | taps | architectures | example | floating point | hardware |
|---|---|---|---|---|---|---|---|
| [A](docs/scenarios/A.md) | adaptive notch | $\cos,\sin$ from phase accumulators and a ROM | $2K$ | A1 serial, A2 direct-form DLMS, A3 folded, A4 lattice IIR notch | LED flicker | 35.38 dB | 35.33 dB |
| [B](docs/scenarios/B.md) | bias canceller | the constant 1 | none | B1 LMS, B2 sign-error, B3 gated; no multiplier | probe-microscopy scan | 34.63 dB | 34.78 dB |
| [C](docs/scenarios/C.md) | canceller without a reference | the row's delayed high band | 128 | C1 serial, C2 folded, C3/C3′ direct-form/systolic DLMS, C4 row-block, C5 DA | drifting stripes | 32.47 dB | 32.48 dB |
| [D](docs/scenarios/D.md) | self-tuning blind-spot predictor | the $5\times5$ window minus its centre | 24 | D1 serial, D2 folded, D3 direct-form DLMS, D4 systolic DLMS, D5 row-block | impulses on texture | 30.99 dB | 30.94 dB |
| [E](docs/scenarios/E.md) | adaptive line enhancer | a larger window minus a blind spot | 48 to 120 | E1 to E5, as D | periodic texture in heavy noise | 29.79 dB | 29.75 dB |
| [F](docs/scenarios/F.md) | reference-sensor canceller | optical-black columns, a reference channel | 1 | F1 frozen, F2 online on the OB pixels, F3 dark-frame calibration | faint astronomical field | 36.28 dB | 36.24 dB |

(Hardware = the exact-LMS engines, or the bias engine for B; B is measured after aligning the mean offset. The
delayed and block engines and the baselines are in each scenario's chapter and in [6.1](docs/06-results.md#61-application-examples).)

<p align="center"><img src="figures/examples/example_C.png" width="100%"></p>
<p align="center"><img src="figures/examples/example_D.png" width="100%"></p>

## What the delay and the block cost

<p align="center"><img src="figures/results/delay_sweep.png" width="100%"></p>

The exact DLMS bound, evaluated with the worst $64\times64$ tile, predicts where the delayed predictor diverges;
the delays of `lms_df` and `lms_systolic` sit well inside it ([1.3](docs/01-foundations.md#images-are-not-stationary)).

<p align="center"><img src="figures/results/rowblock_wordlength.png" width="100%"></p>

Row-block LMS diverges exactly where $\mu N\lambda_{\max,\text{row}}$ crosses 2 and matches exact LMS inside the
bound; a weight register stalls at small steps, the accumulator does not ([6.2](docs/06-results.md#62-row-block-lms)).

## Which architecture for which rate

<p align="center"><img src="figures/results/design_space.png" width="100%"></p>

At 512 x 512 and 30 frames/s a 200 MHz reference clock leaves 25 cycles per pixel, and the exact engines suffice
with 1 to 16 multipliers; at 1080p60 it leaves 1.6, and everything that adapts per pixel needs one of the three
one-pixel-per-clock engines. [Chapter 7](docs/07-choosing.md) turns this into a procedure.

## Repository layout

```
afarch/                 Python models of the hardware
  fxp.py                the arithmetic contract: formats, weight accumulator, rounding, saturation
  engines.py            step-accurate models of exact, delayed and block LMS, and the error unit
  frontends.py          reflected windows, Gaussian high band, tapped delay lines, plane waves, OB means
  scenarios.py          the fixed-point pipelines of A to F, as the RTL tops compute them
  reference.py          floating-point algorithms, PSNR and SSIM
  scenes.py             the corrupted scenes of the examples (fixed seeds)
  lattice.py            architecture A4, the lattice notch (floating point)
  cost.py               time and area formulas, DLMS and block-LMS step bounds
  hdl.py, synth.py      Icarus Verilog and Yosys drivers
rtl/
  common/               lms_arith.vh, lms_err_unit.v, adder_tree.v
  engines/              lms_serial, lms_folded, lms_df, lms_systolic, lms_rowblock, lms_da, lms_engine
  scenarios/            window_gen, scen_a_top ... scen_f_top, cos1024_q12.hex
  baselines/            median3x3_top (median and switching median)
tb/                     testbenches
sim/                    test_engines.py, test_scenarios.py: bit-exact regressions
syn/                    synth_engines.py, synth_tops.py (Yosys), vivado_ooc.tcl (Vivado, timing)
experiments/            delay_sweep, rowblock_wordlength, examples, design_space, diagrams
docs/                   the chapters
results/                csv and json outputs of every script
figures/                diagrams/, examples/, results/
data/                   test images (CC0 / public domain)
scripts/run_all.sh      regenerates every result and figure
```

## Running it

```bash
pip install -r requirements.txt               # numpy, scipy, scikit-image, matplotlib, pillow
sudo apt-get install iverilog yosys           # Icarus Verilog for the RTL tests, Yosys for synthesis

python sim/test_engines.py                    # 24 engine cases + 8 initiation intervals, bit-exact
python sim/test_scenarios.py                  # 32 scenario-top cases, bit-exact
python experiments/examples.py                # the six application examples (about 3 minutes)
python syn/synth_engines.py                   # Yosys cell counts of the engines
bash scripts/run_all.sh                       # everything, in order
```

The results in this repository were produced with Python 3.13, NumPy 2.5, SciPy 1.18, Icarus Verilog 12.0 and
Yosys 0.71. [`syn/vivado_ooc.tcl`](syn/vivado_ooc.tcl) runs any module through Vivado out of context (place, route,
timing); no Vivado result is reported here.

## Citation

GitHub's **Cite this repository** button reads [CITATION.cff](CITATION.cff). In BibTeX:

```bibtex
@software{KhaliliSadaghiani_AdaptiveFilterArchitectures_2026,
  author  = {Khalili Sadaghiani, Abdolvahab},
  title   = {Architectures for Adaptive Filters for Image Denoising},
  year    = {2026},
  url     = {https://github.com/VKHS/Architectures-for-Adaptive-Filters-for-Image-Denoising},
  license = {MIT},
  note    = {ORCID: 0000-0003-4870-2768}
}
```

The algorithms are those of the companion repository:

```bibtex
@software{KhaliliSadaghiani_AdaptiveFilters_2026,
  author  = {Khalili Sadaghiani, Abdolvahab},
  title   = {Adaptive Filters for Image Denoising},
  year    = {2026},
  url     = {https://github.com/VKHS/Adaptive-Filters-for-Image-Denoising},
  license = {MIT},
  note    = {ORCID: 0000-0003-4870-2768}
}
```

## License

The code, RTL, documentation and figures are released under the [MIT License](LICENSE), © 2026 Abdolvahab
Khalili Sadaghiani. The test images in `data/` are CC0 or public domain and keep those terms
([data/README.md](data/README.md)).
