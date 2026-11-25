"""Floating-point references (the algorithms of the companion repository, Adaptive-Filters-for-Image-Denoising),
metrics, baselines and the scenes of the application examples. The hardware models are scored against these.
"""
from pathlib import Path

import numpy as np
from numpy.lib.stride_tricks import sliding_window_view
from scipy.ndimage import gaussian_filter1d, median_filter, convolve1d
from skimage import io as skio

from .frontends import tap_offsets

REPO = Path(__file__).resolve().parents[1]
DATA = REPO / "data"


# ----------------------------------------------------------------------------------------------- images
def to_gray(img):
    img = np.asarray(img)
    if img.dtype == np.uint8:
        img = img.astype(float) / 255.0
    elif img.dtype == np.uint16:
        img = img.astype(float) / 65535.0
    else:
        img = img.astype(float)
    if img.ndim == 3:
        img = img[..., :3] @ np.array([0.2989, 0.5870, 0.1140])
    return img


def load(name="camera"):
    p = DATA / f"{name}.png"
    if not p.exists():
        p = DATA / "examples" / f"{name}.png"
    return to_gray(skio.imread(p))


# ---------------------------------------------------------------------------------------------- metrics
def psnr(ref, est):
    mse = np.mean((np.asarray(ref, float) - np.clip(est, 0, 1)) ** 2)
    return float(10 * np.log10(1.0 / mse))


def offset_aligned_psnr(ref, est):
    e = np.asarray(est, float) - ref
    e = e - e.mean()
    return float(10 * np.log10(1.0 / np.mean(e ** 2)))


def _gauss(img, sigma=1.5, radius=5):
    t = np.arange(-radius, radius + 1)
    g = np.exp(-t ** 2 / (2 * sigma ** 2))
    g /= g.sum()
    return convolve1d(convolve1d(img, g, axis=0, mode="reflect"), g, axis=1, mode="reflect")


def ssim(ref, est):
    x = np.asarray(ref, float)
    y = np.clip(est, 0, 1)
    C1, C2 = 0.01 ** 2, 0.03 ** 2
    mx, my = _gauss(x), _gauss(y)
    sxx, syy, sxy = _gauss(x * x) - mx * mx, _gauss(y * y) - my * my, _gauss(x * y) - mx * my
    s = ((2 * mx * my + C1) * (2 * sxy + C2)) / ((mx ** 2 + my ** 2 + C1) * (sxx + syy + C2))
    return float(s[5:-5, 5:-5].mean())


def median3(img):
    return median_filter(img, size=3, mode="mirror")


def two_state_chain(n, p01, p10, rng):
    pi1 = p01 / (p01 + p10)
    state = int(rng.random() < pi1)
    out = np.empty(n, dtype=np.int8)
    pos = 0
    while pos < n:
        p = p01 if state == 0 else p10
        run = int(np.floor(np.log(1.0 - rng.random()) / np.log(1.0 - p))) + 1
        out[pos:pos + run] = state
        pos += run
        state = 1 - state
    return out


# ------------------------------------------------------------------------------- float algorithms (A-F)
def notch_lms(img, freqs, mu2=1e-3, passes=2):
    """A: two weights per frequency on a raster plane-wave reference; returns the error (cleaned image)."""
    H, W = img.shape
    m = float(img.mean())
    z = img - m
    i, j = np.mgrid[0:H, 0:W]
    refs = np.concatenate([np.stack([np.cos(2 * np.pi * (u * i + v * j)), np.sin(2 * np.pi * (u * i + v * j))], -1)
                           for u, v in freqs], -1)
    w = np.zeros(refs.shape[-1])
    out = np.empty((H, W))
    for _ in range(passes):
        for r in range(H):
            R, d, o = refs[r], z[r], out[r]
            for c in range(W):
                e = d[c] - w @ R[c]
                w += (mu2 * e) * R[c]
                o[c] = e
    return out + m


def bias_canceller(img, mu2=0.02, update="lms", tau=0.08):
    """B: one bias weight along every row, started at the median of the row's first 8 pixels."""
    H, W = img.shape
    out = np.empty((H, W))
    track = np.empty((H, W))
    for r in range(H):
        row = img[r]
        b = float(np.median(row[:8]))
        for c in range(W):
            e = row[c] - b
            out[r, c] = e
            track[r, c] = b
            if update == "lms":
                b += mu2 * e
            elif update == "sign":
                b += mu2 if e > 0 else (-mu2 if e < 0 else 0.0)
            elif -tau < e < tau:
                b += mu2 * e
    return out, track


def subband_canceller(img, L=128, delay=8, alpha=0.002, split_sigma=4.0):
    """C: delayed-reference canceller on the high band of each row; the low band passes untouched."""
    z = img - img.mean(axis=1, keepdims=True)
    high = z - gaussian_filter1d(z, split_sigma, axis=1, mode="reflect")
    mu2 = alpha / (L * float(high.var()))
    H, W = high.shape
    P0 = delay + L - 1
    w = np.zeros(L)
    y = np.empty((H, W))
    for r in range(H):
        p = np.pad(high[r], (P0, 0), mode="reflect")
        X = sliding_window_view(p, L)[:W][:, ::-1]
        d = high[r]
        for c in range(W):
            yc = w @ X[c]
            w += (mu2 * (d[c] - yc)) * X[c]
            y[r, c] = yc
    return img - y


def _row_taps(pad, r, R, W, mflat):
    k = 2 * R + 1
    return sliding_window_view(pad[r:r + k], (k, k))[0].reshape(W, k * k)[:, mflat]


def _mask(R, hole):
    k = 2 * R + 1
    m = np.zeros((k, k), bool)
    for a, b in tap_offsets(R, hole):
        m[a + R, b + R] = True
    return m.ravel()


def blindspot_lms(img, R=2, hole=0, alpha=0.01, mu2=None, passes=2):
    """D / E: blind-spot LMS predictor in raster order; returns the filter output."""
    H, W = img.shape
    m = float(img.mean())
    z = img - m
    mflat = _mask(R, hole)
    nt = int(mflat.sum())
    if mu2 is None:
        mu2 = alpha / (nt * float(z.var()))
    pad = np.pad(z, R, mode="reflect")
    w = np.zeros(nt)
    y = np.empty((H, W))
    for _ in range(passes):
        for r in range(H):
            X = _row_taps(pad, r, R, W, mflat)
            d = z[r]
            for c in range(W):
                yc = w @ X[c]
                w += (mu2 * (d[c] - yc)) * X[c]
                y[r, c] = yc
    return y + m


def blindspot_gated(img, R=2, alpha=0.01, k=4.0, passes=3, t_min=0.1, mu2=None, rate=0.01, scale=1.4826):
    """D gated: replace only pixels whose prediction error exceeds max(k s, t_min); s follows scale * |e| of the
    clean pixels at the given rate. The hardware's gate uses rate 2^-7 and scale 1.5 (afarch.engines.Gate)."""
    H, W = img.shape
    m = float(np.median(img))
    z = img - m
    mflat = _mask(R, 0)
    nt = int(mflat.sum())
    if mu2 is None:
        mu2 = alpha / (nt * float(np.var(np.clip(z, -0.5, 0.5))))
    w = np.full(nt, 1.0 / nt)
    src = z.copy()
    out = z.copy()
    flags = np.zeros((H, W), bool)
    for _ in range(passes):
        pad = np.pad(src, R, mode="reflect")
        s = 0.05
        for r in range(H):
            X = _row_taps(pad, r, R, W, mflat)
            d = z[r]
            for c in range(W):
                yc = w @ X[c]
                e = d[c] - yc
                ae = abs(e)
                if ae > max(k * s, t_min):
                    out[r, c] = yc
                    flags[r, c] = True
                else:
                    out[r, c] = d[c]
                    flags[r, c] = False
                    w += (mu2 * e) * X[c]
                    s += rate * (scale * ae - s)
        src = out.copy()
    return out + m, flags


def train_row_weight(dark, dark_ob, mu2=0.5, passes=3):
    """F: LMS on a dark frame, d = dark pixel, x = optical-black row mean."""
    H, W = dark.shape
    xr = dark_ob.mean(axis=1)
    w = 0.0
    for _ in range(passes):
        for r in range(H):
            x = float(xr[r])
            for c in range(W):
                w += mu2 * (dark[r, c] - w * x) * x
    return w


def channel_reference_canceller(y, ref, dark, dark_ref, alpha=1e-3):
    """F: one-tap canceller with a concurrent reference channel, trained on a dark frame, then frozen."""
    mu2 = alpha / float(np.var(dark_ref))
    w = 0.0
    for d, x in zip(dark.ravel(), dark_ref.ravel()):
        w += mu2 * (d - w * x) * x
    return y - w * ref, w
