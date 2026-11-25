# 7. Choosing an architecture

[Contents](../README.md#contents) · previous: [6. Results](06-results.md) · next: [References](references.md)

Three numbers decide the architecture: the **cycles available per pixel**, $f_{\text{clk}}/R_{\text{px}}$; the **tap
count** $L$; and the **step** against the local signal power, $\mu\lambda_{\max}$ of the worst tile and
$\mu N\lambda_{\max,\text{row}}$ of the worst row. Everything else (the front end, the error unit, the arithmetic)
is the same for every engine.

## 7.1 The procedure

1. **Budget.** $B=f_{\text{clk}}/R_{\text{px}}$ cycles per pixel, with $R_{\text{px}}$ the pixel rate times the number
   of passes per frame. (In a video stream the weights carry over from frame to frame, so one pass per frame is
   the norm; the gated D needs its passes within a frame.)
2. **Exact LMS if it fits.** `lms_serial` if $2L+3\le B$. Otherwise `lms_folded` with the smallest $P$ for which
   $\lceil L/P\rceil+\lceil\log_2P\rceil+5\le B$. If even the floor $\lceil\log_2L\rceil+6$ exceeds $B$, exact LMS is
   impossible at this clock ([1.2](01-foundations.md#12-folding-exact-lms-at-ii--1)).
3. **Otherwise one pixel per clock**, and the algorithm changes:
   * `lms_df` ($D=\lceil\log_2L\rceil+3$) when the taps arrive as a vector (windows: D, E) or the step is large;
   * `lms_systolic` ($D=L+3$) when the taps come from one delay line (C, A) and LUTs matter more than delay;
     check $\mu\lambda_{\max,\text{tile}}<2\sin\frac{\pi}{2(2L+7)}$ with a margin;
   * `lms_rowblock` when the update should leave the pixel loop entirely (filter pipelined freely, update in the
     blanking), if $\mu N\lambda_{\max,\text{row}}\le1$ admits the step you need and 3.2 times the LUTs of `lms_df`
     are acceptable.
4. **No DSP slices left?** `lms_da` at $II=W_D+\lceil\log_2\lceil L/4\rceil\rceil+3$ (22 to 24), paid in LUTs.
5. **Arithmetic:** Q12 data, a Q20 weight view, the 48-bit weight accumulator, $\mu=2^{-S}$ from the normalised step;
   nothing to tune per engine ([chapter 2](02-fixed-point.md)).

## 7.2 The scenarios at three formats

At a 200 MHz reference clock (a reference for the comparison, not a timing result) and one pass per frame:

| | 512 x 512 @ 30 fps, $B=25.4$ | 1024 x 1024 @ 30 fps, $B=6.4$ | 1920 x 1080 @ 60 fps, $B=1.6$ |
|---|---|---|---|
| **A**, $L=4$ | A1 `lms_serial` ($II=11$, 1 DSP) | A2 `lms_df` (8 DSP, $D=5$); folding stops at 8 | A2 `lms_df` |
| **B** | bias engine (no DSP) | bias engine | bias engine |
| **C**, $L=128$ | C2 `lms_folded` $P=8$ ($II=24$, 16 + 16 DSP) or C5 `lms_da` (16 DSP, 36k LUT) | C3 `lms_df` or C3′ `lms_systolic` (256 + 16 DSP) | C3, C3′ or C4 |
| **D**, $L=24$ | D2 `lms_folded` $P=2$ ($II=18$, 4 DSP) | D3 `lms_df` (48 DSP); folding stops at 11 | D3 `lms_df` |
| **D gated**, 3 passes | D3 `lms_df` ($B=8.5$ is below the floor of 11) | D3 `lms_df`, three passes at 94 Mpixel/s | D3, three tops in cascade |
| **E**, $L=48$ | E2 `lms_folded` $P=4$ ($II=19$, 8 DSP) | E3 `lms_df` (96 DSP) | E3 `lms_df` |
| **F**, one tap | F `lms_serial` ($II$ 4 to 5) | F `lms_serial` | F with `lms_df`, $L=1$ (2 DSP) |

Two patterns stand out. At 512 x 512 the exact engines suffice everywhere except the multi-pass gated D, with 1 to
16 multipliers per engine. At 1080p60 everything that adapts per pixel needs one of the three $II=1$ engines,
and the choice among them is the delay and LUT trade-off of chapter 6.

## 7.3 When not to use an LMS engine

* **Unknown or drifting interference frequency, a few lines:** the A4 lattice notch tracks the frequency with one
  coefficient and 5 multipliers ([A](scenarios/A.md#a4-an-iir-notch-that-finds-the-frequency-itself)); C with 128
  taps is the general but expensive answer.
* **A reference of the constant 1:** the bias engine of B has no multiplier at all.
* **Impulses with no multiplier budget:** the switching median (864 LUTs, no DSP) is within 0.9 dB of the gated
  predictor in PSNR on fine texture and slightly ahead in SSIM; it is the baseline any adaptive design must beat
  ([D](scenarios/D.md#results)).
* **A real reference exists:** F, one tap, calibrated on dark frames or online on the optical-black pixels, is
  cheaper and better than inferring the interference from the image (B, C).

## 7.4 A worked example

A 1024 x 1024 camera at 30 frames/s shows vibration stripes of unknown, slowly drifting frequency; the FPGA has
120 DSP slices free and the design is to close at 200 MHz.

* $B=200\cdot10^6/(1024\cdot1024\cdot30)=6.4$ cycles per pixel. C needs $L=128$: the exact floor is 13 cycles, so
  exact LMS is out.
* C3 (`lms_df`) and C3′ (`lms_systolic`) need 256 + 16 DSP slices: out. C5 (`lms_da`) has no DSP, but $II=24$: out.
* The stripes are a single line: **A4**, the lattice notch, tracks the frequency with 5 multipliers (32.66 dB
  against 32.48 dB for C on the drifting-stripe example). It reuses C's front end: the row buffer and the high
  band (16 DSP) on which $k_0$ adapts. Adapting along a row and then filtering it makes two passes per row,
  63 Mpixel/s, inside the budget at one sample per clock.
* The timing risk is the lattice recursion: one multiplier and two adders must close in one 5 ns cycle, which
  has to be checked on the target device before committing to this choice.
* If a second, unrelated line appears later, two lattice sections in cascade still fit; for an arbitrary
  interference spectrum the budget has to grow (a faster clock or more DSP slices for C3).
