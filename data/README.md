# Test images

[Repository](../README.md)

The same images as the companion repository,
[Adaptive Filters for Image Denoising](https://github.com/VKHS/Adaptive-Filters-for-Image-Denoising), as
512 x 512 8-bit grayscale PNGs:

| file | used by | terms |
|---|---|---|
| `camera.png` | examples A.2 (plane waves), C.2 (stripes with a random phase), D.2 (Gaussian noise, $\sigma=20/255$, also the benchmark of the delay and step sweeps); smoke cases of D and E | CC0 |
| `examples/coffee.png` | examples A.1 (LED flicker), C.3 (two tones), F.2 (row banding); smoke case of A | CC0 |
| `examples/chelsea.png` | examples A.3 (mains hum), C.1 (drifting stripes), D.3 (salt and pepper), F.3 (telegraph); smoke case of C | CC0 |
| `examples/gravel.png` | example D.1 (impulses on fine texture); smoke case of D | CC0 |
| `examples/brick.png` | examples E.1 (periodic texture under noise), E.3 (correlated noise) | CC0 |
| `examples/hubble.png` | examples B.2 (CCD readout), F.1 (faint astronomical field); smoke case of F | public domain |

Examples B.1 (probe-microscopy scan), B.3 (printed page) and E.2 (two-tone lattice) use synthetic scenes
([`afarch/scenes.py`](../afarch/scenes.py), [`experiments/example_defs.py`](../experiments/example_defs.py)). The
corruptions are generated with fixed seeds, so every result is reproducible.
