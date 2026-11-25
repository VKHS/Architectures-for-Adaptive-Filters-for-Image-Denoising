"""Architecture A4: adaptive IIR notch in lattice form that tracks the interference frequency itself.

Structure (Regalia's lattice notch): H(z) = (1 + A(z)) / 2 with the second-order allpass

    A(z) = (k1 + k0 (1 + k1) z^-1 + z^-2) / (1 + k0 (1 + k1) z^-1 + k1 z^-2)

realised as a two-stage Gray-Markel lattice (k1 on top, k0 below):

    f1 = x - k1 g1[n-1];   f0 = f1 - k0 g0[n-1];   g0 = f0;   g1 = k0 f0 + g0[n-1];   g2 = k1 f1 + g1[n-1]
    y  = (x + g2) / 2

1 + A(z) has its zeros at exp(+-j w0) with k0 = -cos w0, whatever k1 is; k1 alone sets the bandwidth (the poles
have radius sqrt(k1), the -3 dB width is about 1 - k1 rad/sample). So the frequency is ONE coefficient.

Adaptation of k0 (derived in docs/scenarios/A.md): dy/dk0 = (1 - k1^2)/2 * z^-1 (1 - z^-2) / D(z)^2 x, with
s = x / D(z) = f0 the all-pole state of the lattice. The simplified gradient keeps one 1/D:

    k0 <- k0 - mu y(n) (s(n-1) - s(n-3))

which needs no extra filter (s is in the lattice already). Cost per sample: 4 multipliers (k1 g1[n-1],
k0 g0[n-1], k0 f0, k1 f1) and one for the update. The recursion f0[n-1] -> f0[n] holds a multiplier and two adders,
which bounds the sample rate at 1 / (T_mult + 2 T_add).
"""
import numpy as np


def notch_row(x, k0, k1=0.95, mu=1e-3, adapt=True, state=None):
    """Run the adaptive lattice notch over one 1-D signal. Returns (y, k0 history, final k0, state)."""
    g0d = g1d = 0.0
    s1 = s2 = s3 = 0.0
    if state is not None:
        g0d, g1d, s1, s2, s3 = state
    y = np.empty(len(x))
    kh = np.empty(len(x))
    for n, xn in enumerate(x):
        f1 = xn - k1 * g1d
        f0 = f1 - k0 * g0d
        g1 = k0 * f0 + g0d
        g2 = k1 * f1 + g1d
        yn = 0.5 * (xn + g2)
        y[n] = yn
        if adapt:
            k0 -= mu * yn * (s1 - s3)
            k0 = min(0.999, max(-0.999, k0))
        kh[n] = k0
        s3, s2, s1 = s2, s1, f0
        g0d, g1d = f0, g1
    return y, kh, k0, (g0d, g1d, s1, s2, s3)


def notch_image(img, k0=0.0, k1=0.95, mu=2e-3, preroll=48, highband=True, sigma=4.0):
    """A4 on an image: the notch runs along every row (k0 carried from row to row). The coefficient adapts on the
    high band of the row (where the image is nearly white, as in C), the notch is applied to the full row.
    Each row starts with a reflected pre-roll of ``preroll`` samples that warms the filter state."""
    from scipy.ndimage import gaussian_filter1d
    H, W = img.shape
    m = img.mean(axis=1, keepdims=True)
    z = img - m
    hb = z - gaussian_filter1d(z, sigma, axis=1, mode="reflect") if highband else z
    out = np.empty_like(img)
    ks = np.empty(H)
    for r in range(H):
        idx = np.concatenate([np.arange(preroll, 0, -1), np.arange(W)])
        # adapt on the high band (pre-roll included), then filter the full band with the row's k0
        _, kh, k0, _ = notch_row(hb[r][idx], k0, k1, mu, adapt=True)
        y, _, _, _ = notch_row(z[r][idx], k0, k1, 0.0, adapt=False)
        out[r] = y[preroll:] + m[r]
        ks[r] = k0
    return out, ks
