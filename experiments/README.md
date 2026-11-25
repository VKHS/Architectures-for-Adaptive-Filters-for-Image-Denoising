# experiments/: every result and figure

[Repository](../README.md) · [results](../results/README.md) · [figures](../figures/README.md)

Every number and figure of the chapters comes from one of these scripts, run on the bit-accurate models of
[`afarch`](../afarch/README.md), which the Verilog and the HLS C++ reproduce word for word.
[`scripts/run_all.sh`](../scripts/run_all.sh) runs them in order.

| script | what it computes | outputs | time |
|---|---|---|---|
| [`examples.py`](examples.py) | the 18 application examples: corrupted scene, floating-point algorithm, baselines, every hardware configuration | [`results/examples.csv`](../results/examples.csv), `figures/examples/example_<X>_<k>.png`, `examples_<X>.png`, `overview.png` | about 15 min |
| [`examples_hw.py`](examples_hw.py) | the same configurations through the HLS C++ tops (whole frames) and the Verilog tops (frames, strips, tiles), compared word for word with the models | [`results/examples_hw.csv`](../results/examples_hw.csv) | minutes (HLS), about an hour (RTL) |
| [`example_defs.py`](example_defs.py) | the definitions shared by the two: scenes, floating-point algorithms, configurations, and `run(example, scene, config, impl)` for `impl` = model, rtl or hls | | |
| [`algorithms.py`](algorithms.py) | one illustrated figure per scenario: transfer functions, poles, learning curves, kernels, spectra, Wiener bounds, detection maps, residuals | `figures/algorithms/algorithm_<X>.png`, [`results/algorithms.json`](../results/algorithms.json) | about 8 min |
| [`delay_sweep.py`](delay_sweep.py) | DLMS against the adaptation delay, with the exact bound and the worst tile | [`results/delay_sweep.csv`](../results/delay_sweep.csv), `figures/results/delay_sweep.png` | a few min |
| [`rowblock_wordlength.py`](rowblock_wordlength.py) | block LMS against the step and the row bound; weight register against accumulator | [`results/rowblock_step.csv`](../results/rowblock_step.csv), [`wordlength.csv`](../results/wordlength.csv), [`wordlength_a.csv`](../results/wordlength_a.csv), `figures/results/rowblock_wordlength.png` | a few min |
| [`design_space.py`](design_space.py) | cycles per pixel against multipliers for every engine and the clock each video format needs | [`results/design_space.csv`](../results/design_space.csv), `figures/results/design_space.png` | seconds |
| [`diagrams.py`](diagrams.py) | the block diagrams of the engines, the front ends, the tops, the verification and the HLS structure | `figures/diagrams/*.png` | seconds |
| [`common.py`](common.py) | paths, csv helpers, figure saving | | |

```bash
python experiments/examples.py              # every example, then the figures
python experiments/examples.py A.2 C        # some examples, or a whole scenario; the rest of the csv is kept
python experiments/examples.py --plot       # figures only
python experiments/examples_hw.py --no-rtl  # the examples through the HLS C++ tops
python experiments/examples_hw.py D         # one scenario through both
python experiments/algorithms.py A E        # some algorithm figures
python experiments/diagrams.py verification hls_structure
```

The image archive behind the example figures (`results/examples_images.npz`, about 60 MB) is not kept under
version control; `examples.py --plot` recomputes it when it is missing.
