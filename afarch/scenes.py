"""The corrupted scenes of the application examples (same generators and seeds as the companion repository)."""
import numpy as np

from .reference import load, two_state_chain

LATTICE = ((0.22, 0.071, 0.043, 0.4), (0.14, 0.118, -0.067, 1.1))


def afm_scene(shape=(512, 512), n_obj=60, seed=0, background=0.3):
    rng = np.random.default_rng(seed)
    H, W = shape
    i, j = np.mgrid[0:H, 0:W]
    s = np.full(shape, background)
    for _ in range(n_obj):
        ci, cj = rng.uniform(10, H - 10), rng.uniform(10, W - 10)
        sg = rng.uniform(3.0, 8.0)
        h = rng.uniform(0.25, 0.5)
        s += h * np.exp(-((i - ci) ** 2 + (j - cj) ** 2) / (2 * sg ** 2))
    return np.clip(s, 0, 1)


def scene_a():
    """LED flicker in a rolling-shutter camera: bands at u = 0.0185 cycles/row and its second harmonic."""
    x = load("coffee")
    H, W = x.shape
    rng = np.random.default_rng(11)
    u = 0.0185
    mod = 1 + 0.25 * np.cos(2 * np.pi * u * np.arange(H) + 0.4)[:, None]
    y = x * mod + 0.005 * rng.standard_normal(x.shape)
    return dict(clean=x, noisy=y, freqs=[(u, 0.0), (2 * u, 0.0)])


def scene_b():
    """Probe microscopy: line offsets and a drift along every fast-scan line."""
    rng = np.random.default_rng(7)
    s = afm_scene(n_obj=90, seed=3)
    H, W = s.shape
    j = np.arange(W)[None, :]
    wander = (0.05 + 0.03 * rng.random((H, 1))) * np.sin(2 * np.pi * 0.8 * j / W + 2 * np.pi * rng.random((H, 1)))
    offset = 0.05 * rng.standard_normal((H, 1))
    y = s + offset + wander + 0.1 * j / W + 0.01 * rng.standard_normal(s.shape)
    return dict(clean=s, noisy=y, bias=offset + wander + 0.1 * j / W)


def scene_c():
    """Vibration stripes whose frequency drifts from 0.08 to 0.12 cycles/pixel down the image."""
    x = load("chelsea")
    H, W = x.shape
    ii = np.arange(H)[:, None]
    f = 0.08 + 0.04 * ii / H
    y = x + 0.10 * np.cos(2 * np.pi * np.cumsum(np.repeat(f, W, axis=1), axis=1) + 2 * np.pi * 0.013 * ii)
    return dict(clean=x, noisy=y)


def scene_d():
    """10 % random-valued impulses plus dead and hot pixels on fine texture (gravel)."""
    x = load("gravel")
    rng = np.random.default_rng(5)
    y = x.copy()
    hit = rng.random(x.shape) < 0.10
    y[hit] = rng.random(int(hit.sum()))
    dead = rng.random(x.shape) < 0.005
    y[dead] = (rng.random(int(dead.sum())) < 0.5).astype(float)
    return dict(clean=x, noisy=y, corrupted=hit | dead)


def scene_e():
    """Periodic texture (brick) under heavy white noise, sigma = 0.12."""
    x = load("brick")
    rng = np.random.default_rng(9)
    return dict(clean=x, noisy=x + 0.12 * rng.standard_normal(x.shape))


def scene_f():
    """Faint astronomical field: row banding (with optical-black columns) and readout telegraph noise (with a
    reference output), plus a dark frame for calibration."""
    x = load("hubble")
    H, W = x.shape
    rng = np.random.default_rng(3)

    def telegraph():
        return 0.03 * (2.0 * two_state_chain(H * W, 1 / 60, 1 / 60, rng) - 1.0).reshape(H, W)

    c, t = 0.03 * rng.standard_normal(H), telegraph()
    y = x + c[:, None] + t + 0.01 * rng.standard_normal(x.shape)
    ob = c[:, None] + 0.01 * rng.standard_normal((H, 16))
    ref = 0.8 * t + 0.01 * rng.standard_normal(x.shape)
    cd, td = 0.03 * rng.standard_normal(H), telegraph()
    dark = cd[:, None] + td + 0.01 * rng.standard_normal(x.shape)
    dark_ob = cd[:, None] + 0.01 * rng.standard_normal((H, 16))
    dark_ref = 0.8 * td + 0.01 * rng.standard_normal(x.shape)
    return dict(clean=x, noisy=y, ob=ob, ref=ref, dark=dark, dark_ob=dark_ob, dark_ref=dark_ref)


def camera_gaussian(sigma=20 / 255, seed=1000):
    x = load("camera")
    rng = np.random.default_rng(seed)
    return dict(clean=x, noisy=x + sigma * rng.standard_normal(x.shape))


def camera_periodic(seed=0):
    x = load("camera")
    H, W = x.shape
    i, j = np.mgrid[0:H, 0:W]
    comps = ((0.10, 0.0, 0.0925, 0.7), (0.04, 0.0, 0.1850, 0.3), (0.06, 0.137, 0.061, 1.9))
    p = sum(A * np.cos(2 * np.pi * (u * i + v * j) + ph) for A, u, v, ph in comps)
    rng = np.random.default_rng(10000 + seed)
    return dict(clean=x, noisy=x + p + 0.0 * rng.standard_normal(x.shape), freqs=[(u, v) for _, u, v, _ in comps])


def lattice(shape=(192, 192), seed=31, sigma=0.2):
    H, W = shape
    i, j = np.mgrid[0:H, 0:W]
    lat = 0.5 + sum(A * np.cos(2 * np.pi * (u * i + v * j) + ph) for A, u, v, ph in LATTICE)
    return dict(clean=lat, noisy=lat + sigma * np.random.default_rng(seed).standard_normal(lat.shape))
