# Scenario C: periodic interference without a reference

[Contents](../../README.md#contents) · previous: [B](B.md) · next: [D](D.md)

**The algorithm** ([companion repository, scenario C](https://github.com/VKHS/Adaptive-Filters-for-Image-Denoising/blob/main/docs/C_periodic_noref.md)).
When the interference frequency is unknown and no reference sensor exists, the signal is its own reference after
a delay $\Delta$: a periodic component stays correlated at any delay, a white one does not, so a predictor fed with
$d(n-\Delta-k)$ predicts the interference and not the noise. Natural images are not white, so the predictor runs on
the Gaussian high band of each row ($\sigma=4$), where edges and texture are close to white and the stripes pass
unchanged:

$$h=z-g_\sigma*z,\qquad y(j)=\sum_{k=0}^{127}w_k\,h\big(\mathrm{refl}(j-8-k)\big),\qquad \text{out}(j)=z(j)-y(j),$$

with the weights carried from row to row. The output is the full-band pixel minus the predicted interference
(the error unit's `OUT = 2`); the low band never meets the canceller.

<p align="center"><img src="../../figures/diagrams/scenario_c.png" width="100%"></p>

C is the hardware stress test of the repository: **128 taps**, so $\lceil\log_2L\rceil=7$ adder levels on the
loop, and a tap vector that cannot come from a window but must come from the row's own history. The front end
([4.2](../04-front-ends.md#42-scenario-c-high-band-and-the-reflected-history)) buffers the row, computes the high
band with 16 multipliers (17 symmetric coefficients after the pre-adders; the smallest, 2, is a shift) and streams
the reflected history into the engine.

## Architectures

| code | engine | multipliers (engine) | $II$ | $D$ | cycles per 512-pixel row |
|---|---|---|---|---|---|
| **C1** | `lms_serial` | 1 | 259 | 0 | about 133 300 |
| **C2** | `lms_folded`, $P=8$ | 16 | 24 | 0 | about 13 000 |
| **C3** | `lms_df` (TDL) | 256 | 1 | 10 | about 1 200 |
| **C3′** | `lms_systolic` (TDL), the systolic form of C3 | 256 | 1 | 131 | about 1 200 |
| **C4** | `lms_rowblock` (TDL) | 256 | 1 | one row | about 1 200 |
| **C5** | `lms_da` | 0 | 24 | one row | about 13 000 |

A row costs $W+32$ cycles of high band, $L-1$ pre-roll shifts and $W\cdot II$ cycles of cancelling (plus the
drain of the pipelined engines). At a 200 MHz reference clock (a reference for comparison, not a timing result) a
512 x 512 frame takes 0.34 s with C1, 33 ms with C2 and C5, and 3 ms with C3 and C4: **C2 is the smallest exact
design that just meets 512 x 512 at 30 frames/s** (33.2 ms per frame), and the pipelined engines are needed
beyond that.

Yosys counts for the complete top at $W=512$ ([6.4](../06-results.md#64-synthesis)):

| top | DSP48E1 | LUT | FF | memory |
|---|---|---|---|---|
| C2, `lms_folded` $P=8$ | 32 (16 + 16 high band) | 3757 | 8115 | 2 RAMB18, 144 LUTRAM |
| C3′, `lms_systolic` | 272 (256 + 16) | 6646 | 9836 | 2 RAMB18, 96 LUTRAM |

The engine alone: `lms_df` takes 8145 LUTs at $L=128$, `lms_systolic` 5461 (its adders sit in the DSP cascade),
`lms_rowblock` 26 706 (a second 48-bit accumulator per tap), `lms_da` 36 469 and no DSP slice.

## The price of each way around the loop

**Delay.** The worst $64\times64$ tile has $\mu\lambda_{\max}=0.0023$ at $\mu=2^{-7}$
([1.3](../01-foundations.md#images-are-not-stationary)). `lms_df` ($D=10$, bound 0.149) is 65 times inside the
bound and loses 0.09 dB; `lms_systolic` ($D=131$, bound 0.012) is 5 times inside and loses 0.15 dB. The sweep
over $D$:

| $D$ | 0 | 2 | 4 | 10 | 16 | 32 | 64 | 131 | 256 | 512 |
|---|---|---|---|---|---|---|---|---|---|---|
| PSNR (dB) | 32.48 | 32.45 | 32.43 | 32.39 | 32.39 | 32.38 | 32.36 | 32.33 | 32.46 | 32.74 |

The loss grows slowly up to $D\approx L$. Beyond, the PSNR rises again: at $D=512$ the update computed at a pixel
is applied at the same column of the next row, a schedule close to the row-block update, which suits these
stripes (next paragraph). The bound still holds there ($0.0031$ against $0.0023$); at $D=1024$ it would not.

**Block.** For C the worst row has $512\,\lambda_{\max,\text{row}}=193$, so the row-block engines need $S\ge7$
($\mu N\lambda=1.51$); $S=6$ ($3.02$) diverges, exactly as predicted
([1.4](../01-foundations.md#14-blocking-the-update-row-block-lms)). At $S=7$ the row-block engine gives 32.54 dB,
0.06 dB above exact LMS at the same step (32.48 dB). The examples keep a factor of two from the bound,
$\mu N\lambda_{\max,\text{row}}\le1$, i.e. $S=8$: 32.35 dB.

**Fold.** C2 keeps exact LMS and C5 the block update at $II=24$; they pay in time instead. With the high-band
phase of every row included, 512 x 512 at 30 frames/s needs a clock of about 200 MHz for either.

## Results

Vibration stripes on a photograph, with the frequency drifting from 0.08 to 0.12 cycles/pixel down the image
([examples](../06-results.md#61-application-examples)).

<p align="center"><img src="../../figures/examples/example_C.png" width="100%"></p>

| | class | PSNR |
|---|---|---|
| corrupted | | 23.02 dB |
| floating point | | 32.47 dB |
| C1 `lms_serial`, C2 `lms_folded` ($S=7$) | exact LMS | 32.48 dB |
| C3 `lms_df` ($D=10$) | delayed LMS | 32.39 dB |
| C3′ `lms_systolic` ($D=131$) | delayed LMS | 32.33 dB |
| C4 `lms_rowblock`, C5 `lms_da` ($S=8$) | block LMS | 32.35 dB |
| [A4](A.md#a4-an-iir-notch-that-finds-the-frequency-itself) lattice notch, floating-point model | IIR | 32.66 dB |

C1 and C2 are bit-identical, and so are C4 and C5. What the systolic engine leaves beyond the floating-point
result (difference panel) is stripe residue, within 35 LSB (0.009) on 99.5 % of the pixels.
