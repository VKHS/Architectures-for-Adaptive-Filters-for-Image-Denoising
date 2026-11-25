# 6. Results

[Contents](../README.md#contents) · previous: [5. Verification](05-verification.md) · next: [7. Choosing an architecture](07-choosing.md)

Every image result below is computed with the bit-accurate models, which the RTL reproduces word for word
([chapter 5](05-verification.md)); every resource count is a Yosys result. The scripts that produce them are
named in each section, and their outputs are in [`results/`](../results).

## 6.1 Application examples

Six corrupted scenes, one per scenario, each run through the floating-point algorithm and through the
fixed-point pipeline of its RTL top with several engines
([`experiments/examples.py`](../experiments/examples.py), about 3 minutes; [`results/examples.csv`](../results/examples.csv)).

| | scene and corruption | corrupted | floating point | exact LMS | delayed LMS | block LMS | other |
|---|---|---|---|---|---|---|---|
| [A](scenarios/A.md) | LED flicker bands in a rolling-shutter photo, multiplicative | 22.39 | 35.38 | 35.33 | 35.33 ($D=5$), 35.33 ($D=7$) | | 27.60 without the log domain |
| [B](scenarios/B.md) | line offsets and drift in a probe-microscopy scan | 22.39 | 34.63 | 34.78 (gated) | | | 33.91 sign-error, 28.52 LMS |
| [C](scenarios/C.md) | vibration stripes with drifting frequency | 23.02 | 32.47 | 32.48 | 32.39 ($D=10$), 32.33 ($D=131$) | 32.35 | 32.66 A4 lattice (float model) |
| [D](scenarios/D.md) | 10 % impulses and dead pixels on fine texture | 19.23 | 30.99 | 30.94 | 30.91 ($D=8$), 30.87 ($D=27$) | | 27.32 median, 30.07 switching median |
| [E](scenarios/E.md) | periodic texture under heavy noise, 120 taps | 18.42 | 29.79 | 29.75 | 29.71 ($D=10$), 29.64 ($D=123$) | 29.81 | |
| [F](scenarios/F.md) | row banding and readout telegraph on a faint field | 27.95 | 36.28 | 36.24 | | | 30.20 OB only, 30.17 OB online |

(PSNR in dB; SSIM ([Wang et al. 2004](references.md#wang2004)) is in the csv. B is measured after aligning the mean offset. Exact LMS = `lms_serial` and `lms_folded`, which are
bit-identical; block LMS = `lms_rowblock` and `lms_da`, likewise.)

Three observations hold across the six scenes:

* **Fixed point costs at most 0.06 dB** where the comparison is like for like (A, C, D, E and F against their
  floating-point runs). Q12 data, a Q20 weight view and the 48-bit weight accumulator are enough everywhere
  ([chapter 2](02-fixed-point.md)).
* **The delayed engines are within 0.15 dB of exact LMS** (from +0.005 dB in A to -0.15 dB for the systolic
  engine in C), the loss growing with $D$ while $\mu\lambda_{\max}$ of the worst tile stays well inside the DLMS
  bound ([1.3](01-foundations.md#images-are-not-stationary)).
* **The block engines**, at the step their bound allows ($\mu N\lambda_{\max,\text{row}}\le1$), end 0.13 dB below
  exact LMS at its own step in C (32.35 against 32.48 dB) and 0.06 dB above it in E (29.81 against 29.75 dB).

<p align="center"><img src="../figures/examples/example_A.png" width="100%"></p>
<p align="center"><img src="../figures/examples/example_B.png" width="100%"></p>
<p align="center"><img src="../figures/examples/example_C.png" width="100%"></p>
<p align="center"><img src="../figures/examples/example_D.png" width="100%"></p>
<p align="center"><img src="../figures/examples/example_E.png" width="100%"></p>
<p align="center"><img src="../figures/examples/example_F.png" width="100%"></p>

Each figure shows a crop of the corrupted image, the floating-point result, one hardware result, the difference
between the hardware and floating-point outputs, and the PSNR of every version.

## 6.2 Row-block LMS

[`experiments/rowblock_wordlength.py`](../experiments/rowblock_wordlength.py) sweeps the step of exact and
row-block LMS on the D benchmark (cameraman, Gaussian noise $\sigma=20/255$, 24 taps) and on the C scene (128 taps),
and computes $\mu N\lambda_{\max,\text{row}}$ from the worst row's tap correlation ([`results/rowblock_step.csv`](../results/rowblock_step.csv)):

<p align="center"><img src="../figures/results/rowblock_wordlength.png" width="100%"></p>

| | $S$ | $\mu N\lambda_{\max,\text{row}}$ | exact LMS | row-block LMS |
|---|---|---|---|---|
| D | 9 | 2.87 | 27.12 dB | 7.53 dB (diverged) |
| D | 10 | 1.44 | 27.10 dB | 27.08 dB |
| D | 11 | 0.72 | 27.09 dB | 27.08 dB |
| C | 6 | 3.02 | 32.45 dB | 8.23 dB (diverged) |
| C | 7 | 1.51 | 32.48 dB | 32.54 dB |
| C | 8 | 0.75 | 32.33 dB | 32.35 dB |

The bound $\mu N\lambda_{\max,\text{row}}<2$ separates divergence from convergence in both scenes, with the worst
row's eigenvalue and not the image's: for D the image-wide eigenvalue gives $\mu N\lambda=1.91$ at $S=9$, which
would wrongly predict stability. Inside the bound the two classes agree within 0.07 dB. What the block engines
lose is the large steps: D's best exact step ($S=7$, 27.16 dB) is out of their reach. The right panel is
[2.3](02-fixed-point.md#23-stalling-in-a-weight-register): a weight register with rounded updates stalls at small
steps, the accumulator does not.

## 6.3 Design space

[`experiments/design_space.py`](../experiments/design_space.py) places every engine at the tap counts of D, E and
C by multipliers and cycles per pixel ([`results/design_space.csv`](../results/design_space.csv)):

<p align="center"><img src="../figures/results/design_space.png" width="100%"></p>

The clock that a format needs is $II\times$ pixel rate:

| | $II$ | 512 x 512 @ 30 fps | 1024 x 1024 @ 30 fps | 1920 x 1080 @ 60 fps |
|---|---|---|---|---|
| any engine with $II=1$ | 1 | 7.9 MHz | 31.5 MHz | 124.4 MHz |
| `lms_folded`, $L=24$, $P=8$ to 24 (the floor of exact LMS) | 11 | 86.5 MHz | 346 MHz | 1369 MHz |
| `lms_folded`, $L=24$, $P=6$ | 12 | 94.4 MHz | 377 MHz | 1493 MHz |
| `lms_folded`, $L=128$, $P=8$ | 24 | 189 MHz | 755 MHz | 2986 MHz |
| `lms_da`, $L=128$ | 24 | 189 MHz | 755 MHz | 2986 MHz |
| `lms_serial`, $L=24$ | 51 | 401 MHz | 1604 MHz | 6345 MHz |

(Pixel rates only; the row overheads of the front ends add a few percent, [4](04-front-ends.md).) Folding flattens at
$II=\lceil\log_2L\rceil+6$ (11, 12 and 13 cycles for 24, 48 and 128 taps): **exact LMS cannot reach one pixel per
clock**. At 300 MHz it stops at 27 Mpixel/s for 24 taps; beyond that only the delayed and block engines remain.
That is the practical content of the iteration bound.

## 6.4 Synthesis

[`syn/synth_engines.py`](../syn/synth_engines.py) and [`syn/synth_tops.py`](../syn/synth_tops.py) run Yosys 0.71
`synth_xilinx -family xc7 -flatten` and count the mapped cells ([`results/synth_engines.csv`](../results/synth_engines.csv),
[`results/synth_tops.csv`](../results/synth_tops.csv)). These are technology-mapped counts before placement, not
Vivado utilisation reports, and they carry no timing; [`syn/vivado_ooc.tcl`](../syn/vivado_ooc.tcl) runs the same
modules through Vivado out of context for those who want both.

**Engines** ($W_D=16$, $W_A=48$; TDL = tapped delay line inside the engine):

| engine | $L$ | DSP48E1 | LUT | FF | SRL | LUTRAM |
|---|---|---|---|---|---|---|
| `lms_serial` | 24 / 48 / 128 | 1 / 1 / 1 | 475 / 621 / 1336 | 585 / 972 / 2256 | 0 | 12 / 48 / 48 |
| `lms_folded` $P=2$, $6$ | 24 | 4, 12 | 656, 1295 | 921, 1254 | 0 | 12, 36 |
| `lms_folded` $P=12$ | 48 | 24 | 2549 | 2454 | 0 | 72 |
| `lms_folded` $P=8$, $32$ | 128 | 16, 64 | 2794, 6731 | 4682, 6406 | 0 | 48, 192 |
| `lms_df` | 24 / 48 | 48 / 96 | 1551 / 3069 | 603 / 1181 | 400 / 784 | 0 |
| `lms_df` TDL | 128 | 256 | 8145 | 5199 | 16 | 0 |
| `lms_systolic` | 24 / 48 | 48 / 96 | 1077 / 2085 | 524 / 1028 | 704 / 2448 | 0 |
| `lms_systolic` TDL | 24 / 128 | 48 / 256 | 1093 / 5461 | 1580 / 8564 | 16 / 64 | 0 |
| `lms_rowblock` | 24 / 48 | 48 / 96 | 5032 / 10 030 | 2915 / 5798 | 400 / 784 | 0 |
| `lms_rowblock` TDL | 128 | 256 | 26 706 | 17 497 | 16 | 0 |
| `lms_da` | 24 / 48 / 128 | 0 | 6985 / 13 794 / 36 469 | 4353 / 8561 / 22 585 | 0 | 30 / 60 / 160 |

**Scenario tops** at $W=512$ (front end, engine and error unit):

| top | engine | DSP48E1 | LUT | FF | SRL | LUTRAM | RAMB18 |
|---|---|---|---|---|---|---|---|
| A, $K=2$ | `lms_serial` | 1 | 567 | 434 | 0 | 12 | 2 |
| A, $K=2$ | `lms_df` | 8 | 405 | 373 | 16 | 0 | 2 |
| B, gated | bias engine | 0 | 146 | 73 | 0 | 0 | 0 |
| C, $L=128$ | `lms_folded` $P=8$ | 32 | 3757 | 8115 | 58 | 144 | 2 |
| C, $L=128$ | `lms_systolic` | 272 | 6646 | 9836 | 186 | 96 | 2 |
| D, $L=24$ | `lms_serial` | 1 | 1158 | 1076 | 16 | 12 | 6 |
| D, $L=24$ | `lms_folded` $P=6$ | 12 | 1920 | 1729 | 16 | 36 | 6 |
| D, $L=24$ | `lms_df` | 48 | 2152 | 1075 | 416 | 0 | 6 |
| D gated, $L=24$ | `lms_df` | 48 | 2243 | 1103 | 416 | 0 | 6 |
| E, $L=48$ | `lms_systolic` | 96 | 2557 | 1847 | 2464 | 0 | 8 |
| F | `lms_serial` | 2 | 341 | 330 | 0 | 4 | 0 |
| baseline | median $3\times3$ | 0 | 864 | 228 | 0 | 0 | 4 |

What the tables show:

* **Multipliers land in DSP48E1 slices one to one**, the 24 x 16 update and filter products included. The Gaussian
  of C adds 16, the leave-one-out constant of F one.
* **The weight memory decides the LUTs of the exact engines.** With a single write port the $L$ accumulators of
  `lms_serial` and the lane banks of `lms_folded` map to distributed RAM (`RAM32M`); `lms_serial` grows from 475 to
  1336 LUTs between 24 and 128 taps.
* **The block engines pay for their second accumulator.** `lms_rowblock` needs 3.2 to 3.3 times the LUTs of
  `lms_df` at every $L$; `lms_da` needs no DSP slice but 6985 to 36 469 LUTs, at $II=22$ to 24.
* **The systolic engine is the leanest pipelined engine in logic** (its adders sit in the DSP cascade), and the
  most expensive in delay lines when its taps arrive as a vector (E).
* **Front ends are cheap.** Row buffers map to one RAMB18 each; the whole D top with `lms_df` is 601 LUTs more than
  the bare engine.
