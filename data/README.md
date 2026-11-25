# Test images

The same images as the companion repository,
[Adaptive Filters for Image Denoising](https://github.com/VKHS/Adaptive-Filters-for-Image-Denoising), as
512 x 512 8-bit grayscale PNGs:

| file | used by | terms |
|---|---|---|
| `camera.png` | the D benchmark (Gaussian noise, $\sigma=20/255$) of the delay and step sweeps | CC0 |
| `examples/coffee.png` | example A, LED flicker | CC0 |
| `examples/chelsea.png` | example C, drifting stripes | CC0 |
| `examples/gravel.png` | example D, impulses on fine texture | CC0 |
| `examples/brick.png` | example E, periodic texture under noise | CC0 |
| `examples/hubble.png` | example F, faint astronomical field | public domain |

Example B uses a synthetic probe-microscopy scan (`afarch/scenes.py`). The corruptions are generated with fixed
seeds by `afarch/scenes.py`, so every result is reproducible.
