# results/: the numbers behind the chapters

[Repository](../README.md) · [experiments](../experiments/README.md)

Written by the scripts of [`experiments/`](../experiments/README.md), [`sim/`](../sim/README.md),
[`smoke/`](../smoke/README.md) and [`syn/`](../syn/README.md). PSNR in dB against the clean image; codes and
residuals in LSB of Q12 (4096 = 1.0).

| file | written by | columns / contents |
|---|---|---|
| [`examples.csv`](examples.csv) | `experiments/examples.py` | `example` (A.1 .. F.3), `method`, `cls` (float, exact LMS, delayed LMS, block LMS, bias, baseline, dedicated), `psnr`, `ssim`, `key` (image in the archive) |
| [`examples_hw.csv`](examples_hw.csv) | `experiments/examples_hw.py` | `example`, `config`, `cls`, `impl` (HLS C++ or RTL), `region` (whole frame, strip or tile), `words` compared, `match`, `psnr_model`, `psnr_impl` (on the region), run times, `ap_int` |
| [`algorithms.json`](algorithms.json) | `experiments/algorithms.py` | the numbers quoted in the algorithm sections: notch bandwidths, pole radii, learned amplitudes, track errors, detection rates, Wiener bounds, weights, residuals |
| [`smoke.json`](smoke.json) | `smoke/smoke.py` | per case: scenario, engine, pixels, configuration, RTL and HLS verdicts |
| [`rtl_engine_tests.json`](rtl_engine_tests.json) | `sim/test_engines.py` | per case: engine, taps, samples, flagged samples, match; per handshake engine: measured and predicted II, first-output latency |
| [`rtl_scenario_tests.json`](rtl_scenario_tests.json) | `sim/test_scenarios.py` | per case: scenario, engine, configuration, pixels, outputs, match |
| [`synth_engines.csv`](synth_engines.csv) | `syn/synth_engines.py` | `engine`, `L`, `P`, `TDL`, DSP48E1, LUT, FF, SRL, LUTRAM, RAMB18, RAMB36, CARRY4, MUXF, seconds |
| [`synth_tops.csv`](synth_tops.csv) | `syn/synth_tops.py` | `scenario`, `top`, `engine` and the same cell counts, at $W=512$ |
| [`delay_sweep.csv`](delay_sweep.csv) | `experiments/delay_sweep.py` | `scenario`, `L`, `S`, `D`, PSNR, $\mu\lambda$ (image and worst tile), the DLMS bound |
| [`rowblock_step.csv`](rowblock_step.csv) | `experiments/rowblock_wordlength.py` | `scenario`, `engine`, `S`, PSNR, $\mu\lambda$, $\mu N\lambda$, $\mu N\lambda_{\max,\text{row}}$ |
| [`wordlength.csv`](wordlength.csv), [`wordlength_a.csv`](wordlength_a.csv) | `experiments/rowblock_wordlength.py` | weight register against accumulator: `storage`, `FW`, `WW`, `S`, PSNR |
| [`design_space.csv`](design_space.csv) | `experiments/design_space.py` | `scenario`, `L`, `engine`, `P`, multipliers, II, $D$, LUT, FF, DSP, the clock for three video formats |
| `examples_images.npz` | `experiments/examples.py` | the images of the example figures (not under version control) |
