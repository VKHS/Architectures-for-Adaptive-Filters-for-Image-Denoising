# Scenario D: self-tuning blind-spot predictor

[Contents](../../README.md#contents) · previous: [C](C.md) · next: [E](E.md)

**The algorithm** ([companion repository, scenario D](https://github.com/VKHS/Adaptive-Filters-for-Image-Denoising/blob/main/docs/D_self_tuning.md)).
Pixel $(i,j)$ is predicted from its $5\times5$ neighbourhood with the centre left out (24 taps):

$$y(i,j)=\sum_{(a,b)\ne(0,0)}w_{ab}\,d(i+a,j+b),\qquad e(i,j)=d(i,j)-y(i,j).$$

White noise in the centre pixel is uncorrelated with every tap, so minimising $E[e^2]$ is the same as minimising
the error against the clean image, which is never seen. The filter output $y$ is the image estimate. For sparse
noise (impulses, dead pixels) the **gated** variant uses $e$ as a detector: a pixel is flagged when
$|e|>\max(k\hat\sigma_e,t_{\min})$, flagged pixels are replaced by $y$, clean ones pass unchanged, only clean
pixels adapt, and a later pass takes its taps from the previous pass's output.

## Architecture

[`scen_de_top`](../../rtl/scenarios/scen_de_top.v) chains the window generator, any of the six engines and the
shared error unit:

```
pixel ─▶ − off ─▶ window_gen (2R+1)², reflected borders ─▶ taps without the (2H+1)² centre ─▶ engine ─▶ y or (flag ? y : d) ─▶ + off
```

* **Window.** [`window_gen`](../04-front-ends.md#41-borders-without-padding-reflected-addressing) with $R=2$: six
  row buffers (six RAMB18 at $W=512$, two 16-bit planes each) and a $5\times5$ register window. The tap
  selection is wiring: a constant function `tap_index` maps window positions to taps and drops the blind spot.
* **Centring.** The pixels are centred on an offset (the image median for the gated filter, the mean otherwise),
  which is an input of the top; in a video stream it is the previous frame's value.
* **Gate.** The error unit with `OUT = 3` and `GATED = 1`
  ([3.7](../03-engines.md#37-the-shared-error-unit)): a running scale $s$ with 8 fraction bits, rate $2^{-7}$,
  threshold $\max((s\gg8)\ll2,\ 410)$, i.e. $k=4$ and $t_{\min}=0.1$, and no multiplier. It costs 91 LUTs and 28
  flip-flops over the plain predictor (Yosys, `lms_df` top). The weights start at $1/L$ (`A0`), a mean filter,
  so the gate works from the first pixel.
* **Passes.** The window generator carries two planes, the tap source and the desired pixel. The second and third
  passes stream the frame again with the previous output as tap source, so the gated filter at three passes
  needs a frame buffer and three times the pixel rate. A cascade of three tops would need only row buffers, but
  each pass would then start from its own weights; the model and the results below carry one set of weights
  through the passes.

| code | engine | multipliers | $II$ | $D$ | top at $W=512$ (Yosys) |
|---|---|---|---|---|---|
| **D1** | `lms_serial` | 1 | 51 | 0 | 1 DSP, 1158 LUT, 6 RAMB18 |
| **D2** | `lms_folded`, $P=6$ | 12 | 12 | 0 | 12 DSP, 1920 LUT, 6 RAMB18 |
| **D3** | `lms_df` | 48 | 1 | 8 | 48 DSP, 2152 LUT, 6 RAMB18 (gated: 2243 LUT) |
| **D4** | `lms_systolic` | 48 | 1 | 27 | (engine: 48 DSP, 1077 LUT, 704 SRL) |
| **D5** | `lms_rowblock` | 48 | 1 | one row | (engine: 48 DSP, 5032 LUT) |
| baseline | median $3\times3$ / switching median | 0 | 1 | | 0 DSP, 864 LUT, 4 RAMB18 |

The window generator needs $W+2R$ read cycles per row, so the pipelined engines see 4 blanking cycles per row at
$R=2$. At the 200 MHz reference clock, D1 handles about 3.9 Mpixel/s, a 512 x 512 frame in 67 ms; D2 handles
16.7 Mpixel/s, enough for 512 x 512 at 30 frames/s with two passes; the pipelined engines handle the full clock
rate.

The [median baseline](../../rtl/baselines/median3x3_top.v) uses the same window generator with $R=1$ and the
19 compare-exchange network of [Paeth and Devillard](../references.md#devillard1998) for the median of nine; its
switching form replaces only the pixels farther than a threshold from the median.

## Delay, block and word length

These sweeps use the benchmark of the companion repository, the cameraman with Gaussian noise
($\sigma=20/255$), and the plain (non-gated) predictor at $\mu=2^{-8}$ ([1.3](../01-foundations.md#images-are-not-stationary)):

* **Delay.** The worst $64\times64$ tile has $\mu\lambda_{\max}=0.019$. D3 ($D=8$, bound 0.185) costs 0.003 dB and
  D4 ($D=27$, bound 0.057) 0.02 dB. The bound reaches $0.019$ between $D=64$ and $D=128$, where the predictor
  diverges.
* **Block.** The worst row has $512\,\lambda_{\max,\text{row}}=1472$, so D5 needs $S\ge10$ ($\mu N\lambda=1.44$);
  $S=9$ ($2.87$) diverges. At $S=10$ D5 gives 27.08 dB, against 27.16 dB for exact LMS at its best step $S=7$:
  the block engine pays for the smaller step it is forced to take.
* **Word length.** With the weight accumulator, 10 fraction bits in the weight view and 8 in the data lose nothing
  measurable (27.145 and 27.143 dB against 27.145 dB). A weight register with rounded updates loses 0.18 dB at
  $F_W=10$ ([2.3](../02-fixed-point.md#23-stalling-in-a-weight-register)).

## Results

Fine texture (gravel) with 10 % random-valued impulses and 0.5 % dead and hot pixels
([examples](../06-results.md#61-application-examples)), gated predictor, three passes:

<p align="center"><img src="../../figures/examples/example_D.png" width="100%"></p>

| | PSNR | SSIM |
|---|---|---|
| corrupted | 19.23 dB | 0.593 |
| floating point, gated | 30.99 dB | 0.944 |
| D1 `lms_serial`, gated (exact LMS) | 30.94 dB | 0.943 |
| D3 `lms_df`, gated ($D=8$) | 30.91 dB | 0.943 |
| D4 `lms_systolic`, gated ($D=27$) | 30.87 dB | 0.943 |
| median $3\times3$ | 27.32 dB | 0.881 |
| switching median, threshold 0.15 (best PSNR of 0.05 to 0.2) | 30.07 dB | 0.947 |

The gated predictor beats the median by 3.6 dB and the best switching median by 0.9 dB in PSNR; in SSIM the
switching median is slightly ahead (0.947 against 0.943). It is the cheap alternative (no multiplier, 864 LUTs)
and shares the idea of replacing only outliers. Its detector even finds more of the impulses (84 % of those that
deviate by more than 0.1, against 76 % in the predictor's last pass), but it also flags 1.0 % of the clean
pixels, against 0.06 %: on fine texture a clean pixel is often far from the median of its neighbours, and every
false alarm replaces it by that median. Which measure matters, squared error or local structure, decides whether
the multipliers are worth it.
