# docs/: the chapters

[Repository](../README.md)

| | chapter | contents |
|---|---|---|
| 1 | [From the LMS loop to an architecture](01-foundations.md) | the iteration bound; folding; delayed LMS and its exact stability bound; block LMS and its bound; the worst tile and the worst row |
| 2 | [Fixed point](02-fixed-point.md) | Q12 data, Q20 weights, the 48-bit weight accumulator, stalling, word growth |
| 3 | [The six engines](03-engines.md) | `lms_serial`, `lms_folded`, `lms_df`, `lms_systolic`, `lms_rowblock`, `lms_da`, the error unit |
| 4 | [Front ends](04-front-ends.md) | reflected windows, C's high band and reflected history, plane waves, optical-black references |
| A | [Adaptive notch](scenarios/A.md) | known frequencies, synthetic references, the notch, the lattice notch A4 |
| B | [Bias canceller](scenarios/B.md) | the constant reference, LMS, sign-error and gated updates |
| C | [Canceller without a reference](scenarios/C.md) | prediction across a delay, the two-band split, 128 taps |
| D | [Self-tuning blind-spot predictor](scenarios/D.md) | the blind spot, the gate, impulses and Gaussian noise |
| E | [Adaptive line enhancer](scenarios/E.md) | the ALE gain and its Wiener bound, the blind spot against correlated noise |
| F | [Reference-sensor canceller](scenarios/F.md) | optical-black columns, the reference channel, dark frames, leave-one-out |
| 5 | [Verification](05-verification.md) | regressions, smoke tests, the examples through the Verilog and the HLS C++ |
| 6 | [Results](06-results.md) | the 18 examples, row-block LMS, design space, synthesis |
| 7 | [Choosing an architecture](07-choosing.md) | a procedure, three video formats, a worked example |
| | [References](references.md) | with DOIs |

Every scenario chapter has the same six sections:

1. **The problem**: the signal model.
2. **The algorithm**: the derivations, with a figure computed on the models
   (`figures/algorithms/algorithm_<X>.png`).
3. **The architecture (RTL)**: the top, its architectures, their cost, ports and parameters.
4. **The HLS C++ implementation**: the top function, its loops and pragmas, its configuration, synthesis targets.
5. **Examples**: three corrupted scenes, each with its figure, its PSNR and SSIM for every engine, and the record of
   the Verilog and HLS C++ runs that reproduce it word for word.
6. **Smoke test**: the cases of [`smoke/smoke.py`](../smoke/README.md) for the scenario.
