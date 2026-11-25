"""The eighteen application examples, three per scenario (A.1 .. F.3): scenes, floating-point algorithms, and the
hardware configurations that run them. (Example A.2 is not architecture A2: the architectures of a scenario are
numbered without a dot, docs/scenarios.)

experiments/examples.py evaluates every configuration on the bit-accurate models; experiments/examples_hw.py runs
the configurations marked rtl / hls through the Verilog tops (Icarus Verilog) and the HLS C++ tops (g++ C
simulation) and checks that every output word equals the model's. Both go through run(), so the three
implementations see exactly the same input codes:

    run(example, scene, config, impl)   impl = "model" | "rtl" | "hls"   ->  (output image, raw output words)

The raw words are what the top writes (for A in the log domain: before the exp ROM; for D/E: pixel and gate flag;
for B: output and bias track).
"""
from dataclasses import dataclass, field

import numpy as np
from scipy.ndimage import gaussian_filter1d

import common  # noqa: F401  (puts the repository on the path)
from afarch import scenarios as sc, scenes, reference as ref, lattice, frontends as fe, hwrun, hdl
from afarch.cost import worst_row_lambda, block_step
from afarch.fxp import Arith, step_exponent

WORK = hdl.BUILD / "examples_hw"


@dataclass
class Config:
    """One hardware configuration of an example."""
    label: str                 # shown in tables and bar charts
    cls: str                   # exact LMS | delayed LMS | block LMS | bias
    kind: str                  # a | b | c | de | f_ob | f_online | f_channel | f_ob_channel
    kw: dict                   # parameters of the scenario model
    key: bool = False          # the configuration shown in the example figure
    rtl: bool = False          # run through the RTL top in examples_hw.py
    hls: bool = True           # run through the HLS top in examples_hw.py


@dataclass
class Example:
    id: str
    title: str
    scene: callable
    floats: list               # (label, fn(scene) -> image)
    configs: list
    baselines: list = field(default_factory=list)
    aligned: bool = False      # B: PSNR after aligning the mean offset
    cols: slice = slice(None)  # columns scored (B2 leaves its prescan out)
    crop: tuple = (slice(None), slice(None))
    disp: str = None           # None | "afm" | "astro" | "page"
    rtl_rows: slice = slice(None)   # the part of the frame examples_hw.py streams through the RTL: Icarus is
    rtl_cols: slice = slice(None)   # slow for the wide engines, so C runs a strip and D and E a tile

    @property
    def scenario(self):
        return self.id[0]


# ---------------------------------------------------------------------------------------------- scenes
def scene_a3():
    """Mains hum in a raster readout: a 1-D hum at 0.0137 cycles per pixel clock, 600 clocks per line (512
    pixels and 88 of blanking), is a plane wave of the image with u = frac(600 v): (0.22, 0.0137) and its third
    harmonic (0.66, 0.0411)."""
    x = ref.load("chelsea")
    H, W = x.shape
    v1, line = 0.0137, 600
    u1 = (line * v1) % 1.0
    n = np.arange(H)[:, None] * line + np.arange(W)[None, :]
    hum = 0.07 * np.cos(2 * np.pi * v1 * n + 0.3) + 0.03 * np.cos(2 * np.pi * 3 * v1 * n + 1.1)
    y = x + hum + 0.004 * np.random.default_rng(2).standard_normal(x.shape)
    return dict(clean=x, noisy=y, freqs=[(u1, v1), ((3 * u1) % 1.0, 3 * v1)])


PRESCAN = 16


def scene_b2():
    """A CCD frame of a faint field: every row starts with 16 prescan pixels (no light), and carries an offset and
    a slow wander from the readout electronics."""
    x0 = ref.load("hubble")
    H, W = x0.shape
    x = np.concatenate([np.zeros((H, PRESCAN)), x0[:, :W - PRESCAN]], 1)
    rng = np.random.default_rng(17)
    j = np.arange(W)[None, :]
    bias = 0.04 * rng.standard_normal((H, 1)) + 0.03 * np.sin(
        2 * np.pi * (0.5 + rng.random((H, 1))) * j / W + 2 * np.pi * rng.random((H, 1)))
    return dict(clean=x, noisy=x + bias + 0.008 * rng.standard_normal(x.shape), bias=bias)


def page(shape=(512, 512), seed=21):
    """A synthetic printed page: lines of glyph-like strokes, dark ink on light paper."""
    rng = np.random.default_rng(seed)
    H, W = shape
    s = np.full(shape, 0.88)
    for top in range(14, H - 16, 22):
        j = 16
        while j < W - 20:
            gw = int(rng.integers(5, 10))
            if rng.random() < 0.16:
                j += gw
                continue
            for _ in range(int(rng.integers(2, 4))):
                if rng.random() < 0.55:
                    c = j + int(rng.integers(0, gw - 1))
                    s[top:top + 11, c:c + 2] = 0.12
                else:
                    r = top + int(rng.integers(0, 10))
                    s[r:r + 2, j:j + gw - 1] = 0.12
            j += gw + 2
    return s


def scene_b3():
    """A scanned page: each scan line has its own offset and an illumination wander along it."""
    x = page()
    H, W = x.shape
    rng = np.random.default_rng(23)
    j = np.arange(W)[None, :]
    bias = 0.05 * rng.standard_normal((H, 1)) + 0.08 * np.cos(
        2 * np.pi * j / W * 0.7 + 2 * np.pi * rng.random((H, 1))) * (0.5 + rng.random((H, 1)))
    return dict(clean=x, noisy=x + bias + 0.01 * rng.standard_normal(x.shape), bias=bias)


def scene_c2():
    """Stripes at a fixed 0.1 cycles/pixel, with a random phase on every row (no plane wave: A cannot model it)."""
    x = ref.load("camera")
    H, W = x.shape
    rng = np.random.default_rng(41)
    j = np.arange(W)[None, :]
    return dict(clean=x, noisy=x + 0.10 * np.cos(2 * np.pi * 0.1 * j + 2 * np.pi * rng.random((H, 1))))


def scene_c3():
    """Two interference tones along the rows, 0.07 and 0.16 cycles/pixel, one coherent, one with a random phase
    per row."""
    x = ref.load("coffee")
    H, W = x.shape
    rng = np.random.default_rng(43)
    j = np.arange(W)[None, :]
    i = np.arange(H)[:, None]
    y = x + 0.06 * np.cos(2 * np.pi * 0.07 * j + 2 * np.pi * 0.011 * i) + 0.05 * np.cos(
        2 * np.pi * 0.16 * j + 2 * np.pi * rng.random((H, 1)))
    return dict(clean=x, noisy=y)


def scene_d3():
    """20 % salt-and-pepper impulses (0 or 1)."""
    x = ref.load("chelsea")
    rng = np.random.default_rng(13)
    y = x.copy()
    hit = rng.random(x.shape) < 0.20
    y[hit] = (rng.random(int(hit.sum())) < 0.5).astype(float)
    return dict(clean=x, noisy=y, corrupted=hit)


def scene_e3():
    """Brick under spatially correlated noise: white noise through a 2 x 2 box, correlated at lag 1 only."""
    x = ref.load("brick")
    rng = np.random.default_rng(29)
    w = rng.standard_normal((x.shape[0] + 1, x.shape[1] + 1))
    n = (w[:-1, :-1] + w[1:, :-1] + w[:-1, 1:] + w[1:, 1:]) / 2.0
    return dict(clean=x, noisy=x + 0.10 * n)


def scene_f2():
    """Row banding on a camera sensor, with 16 optical-black columns per row and a dark frame."""
    x = ref.load("coffee")
    H, W = x.shape
    rng = np.random.default_rng(5)
    c = 0.03 * rng.standard_normal(H)
    cd = 0.03 * rng.standard_normal(H)
    return dict(clean=x, noisy=x + c[:, None] + 0.01 * rng.standard_normal(x.shape),
                ob=c[:, None] + 0.01 * rng.standard_normal((H, 16)),
                dark=cd[:, None] + 0.01 * rng.standard_normal(x.shape),
                dark_ob=cd[:, None] + 0.01 * rng.standard_normal((H, 16)), banding=c)


def scene_f3():
    """Readout telegraph noise with a reference output that sees 0.8 of it, and a dark frame."""
    x = ref.load("chelsea")
    H, W = x.shape
    rng = np.random.default_rng(8)

    def tel():
        return 0.03 * (2.0 * ref.two_state_chain(H * W, 1 / 60, 1 / 60, rng) - 1.0).reshape(H, W)

    t = tel()
    y = x + t + 0.01 * rng.standard_normal(x.shape)
    rf = 0.8 * t + 0.01 * rng.standard_normal(x.shape)
    td = tel()
    return dict(clean=x, noisy=y, ref=rf, dark=td + 0.01 * rng.standard_normal(x.shape),
                dark_ref=0.8 * td + 0.01 * rng.standard_normal(x.shape), telegraph=t)


# ------------------------------------------------------------------------------------------ step sizes
def c_tap_rows(hi, L=128, delay=8):
    """Float tap matrices of C, row by row: x_k(j) = h(refl(j - delay - k)) as in the RTL front end."""
    from numpy.lib.stride_tricks import sliding_window_view
    W = hi.shape[1]
    return (sliding_window_view(np.pad(hi[r], (L - 1 + delay, 0), mode="reflect"), L)[:W][:, ::-1]
            for r in range(hi.shape[0]))


def c_steps(y, alpha=0.005):
    """C: the power-of-two step of the per-pixel engines and the block step (mu N lambda_max,row <= 1)."""
    zc = y - y.mean(axis=1, keepdims=True)
    hi = zc - gaussian_filter1d(zc, 4.0, axis=1, mode="reflect")
    return step_exponent(alpha, 128, hi.var()), block_step(worst_row_lambda(c_tap_rows(hi)), y.shape[1])


def de_steps(y, R, H=0, alpha=0.01, gated=False):
    """D / E: the power-of-two step (normalised by L and the tap power) and the block step."""
    z = y - (np.median(y) if gated else y.mean())
    L = len(fe.tap_offsets(R, H))
    S = step_exponent(alpha, L, np.var(np.clip(z, -0.5, 0.5)) if gated else z.var())
    X = fe.window_taps(z, R, H).astype(float).reshape(y.shape[0], y.shape[1], -1)
    return S, block_step(worst_row_lambda(X[r] for r in range(y.shape[0])), y.shape[1])


def f_channel_step(s):
    return int(round(-np.log2(1e-3 / np.var(s["dark_ref"]))))


# ------------------------------------------------------------------------------------------- examples
def _a(label, cls, S, passes, log, engine, **kw):
    return Config(label, cls, "a", dict(S=S, passes=passes, log=log, engine=engine), **kw)


def _de(label, cls, engine, S, R, H=0, passes=2, gated=False, **kw):
    return Config(label, cls, "de", dict(S=S, R=R, H=H, passes=passes, gated=gated, engine=engine), **kw)


def build():
    """The examples, with the steps that depend on the scenes computed here (a few seconds)."""
    ex = []
    # ---------------------------------------------------------------------------------------------- A
    ex.append(Example(
        "A.1", "LED flicker in a rolling-shutter camera", scenes.scene_a,
        [("float (log domain)", lambda s: np.exp(ref.notch_lms(np.log(np.clip(s["noisy"], 0, None) + 0.02),
                                                                  s["freqs"], mu2=1e-5, passes=3)) - 0.02)],
        [_a("serial, log domain", "exact LMS", 17, 3, True, "serial", key=True, rtl=True),
         _a("folded, log domain", "exact LMS", 17, 3, True, "folded"),
         _a("df, log domain", "delayed LMS", 17, 3, True, "df", rtl=True),
         _a("systolic, log domain", "delayed LMS", 17, 3, True, "systolic"),
         _a("serial, linear domain", "exact LMS", 17, 3, False, "serial")],
        crop=(slice(0, 512), slice(0, 512))))
    ex.append(Example(
        "A.2", "three plane waves on a photograph", scenes.camera_periodic,
        [("float", lambda s: ref.notch_lms(s["noisy"], s["freqs"], mu2=2 ** -12, passes=2))],
        [_a("serial", "exact LMS", 12, 2, False, "serial", rtl=True),
         _a("folded", "exact LMS", 12, 2, False, "folded"),
         _a("df", "delayed LMS", 12, 2, False, "df", key=True, rtl=True),
         _a("systolic", "delayed LMS", 12, 2, False, "systolic")],
        crop=(slice(60, 316), slice(140, 396))))
    ex.append(Example(
        "A.3", "mains hum in a raster readout", scene_a3,
        [("float", lambda s: ref.notch_lms(s["noisy"], s["freqs"], mu2=2 ** -12, passes=2))],
        [_a("serial", "exact LMS", 12, 2, False, "serial", key=True, rtl=True),
         _a("df", "delayed LMS", 12, 2, False, "df", rtl=True),
         _a("systolic", "delayed LMS", 12, 2, False, "systolic")],
        crop=(slice(120, 376), slice(160, 416))))
    # ---------------------------------------------------------------------------------------------- B
    ex.append(Example(
        "B.1", "line offsets and drift in a probe-microscopy scan", scenes.scene_b,
        [("float, gated", lambda s: ref.bias_canceller(s["noisy"], 0.05, "gated", tau=0.08)[0]),
         ("float, LMS", lambda s: ref.bias_canceller(s["noisy"], 0.02, "lms")[0])],
        [Config("bias engine, gated", "bias", "b", dict(S=4, mode="gated", sk=0, tau=0.08), key=True, rtl=True),
         Config("bias engine, LMS", "bias", "b", dict(S=6, mode="lms", sk=0, tau=0.08), rtl=True),
         Config("bias engine, sign-error", "bias", "b", dict(S=4, mode="sign", sk=6, tau=0.08), rtl=True)],
        aligned=True, disp="afm"))
    ex.append(Example(
        "B.2", "offsets and wander of a CCD readout, faint field", scene_b2,
        [("float, gated", lambda s: ref.bias_canceller(s["noisy"], 2 ** -4, "gated", tau=0.08)[0]),
         ("float, sign-error", lambda s: ref.bias_canceller(s["noisy"], 2 ** -10, "sign")[0])],
        [Config("bias engine, gated", "bias", "b", dict(S=4, mode="gated", sk=0, tau=0.08), key=True, rtl=True),
         Config("bias engine, sign-error", "bias", "b", dict(S=4, mode="sign", sk=6, tau=0.08), rtl=True),
         Config("bias engine, LMS", "bias", "b", dict(S=6, mode="lms", sk=0, tau=0.08), rtl=True)],
        aligned=True, cols=slice(PRESCAN, None), crop=(slice(150, 406), slice(0, 256)), disp="astro"))
    ex.append(Example(
        "B.3", "scan-line offsets and illumination wander on a page", scene_b3,
        [("float, gated", lambda s: ref.bias_canceller(s["noisy"], 2 ** -4, "gated", tau=0.08)[0]),
         ("float, LMS", lambda s: ref.bias_canceller(s["noisy"], 0.02, "lms")[0])],
        [Config("bias engine, gated", "bias", "b", dict(S=4, mode="gated", sk=0, tau=0.08), key=True, rtl=True),
         Config("bias engine, sign-error", "bias", "b", dict(S=4, mode="sign", sk=6, tau=0.08), rtl=True),
         Config("bias engine, LMS", "bias", "b", dict(S=6, mode="lms", sk=0, tau=0.08), rtl=True)],
        aligned=True, crop=(slice(0, 256), slice(0, 256)), disp="page"))
    # ---------------------------------------------------------------------------------------------- C
    for eid, title, scene, crop in (
            ("C.1", "vibration stripes whose frequency drifts", scenes.scene_c, (slice(100, 356), slice(100, 356))),
            ("C.2", "stripes with a random phase on every row", scene_c2, (slice(40, 296), slice(150, 406))),
            ("C.3", "two interference tones along the rows", scene_c3, (slice(100, 356), slice(150, 406)))):
        s = scene()
        S, Sb = c_steps(s["noisy"])
        cfg = [Config("serial", "exact LMS", "c", dict(S=S, engine="serial")),
               Config("folded", "exact LMS", "c", dict(S=S, engine="folded"), rtl=True),
               Config("df", "delayed LMS", "c", dict(S=S, engine="df")),
               Config("systolic", "delayed LMS", "c", dict(S=S, engine="systolic"), key=True),
               Config(f"rowblock (S = {Sb})", "block LMS", "c", dict(S=Sb, engine="rowblock")),
               Config(f"da (S = {Sb})", "block LMS", "c", dict(S=Sb, engine="da"))]
        ex.append(Example(
            eid, title, scene, [("float", lambda s: ref.subband_canceller(s["noisy"], alpha=0.005))], cfg,
            baselines=[("A4 lattice notch (float model)", "dedicated",
                        lambda s: lattice.notch_image(s["noisy"], k1=0.9, mu=0.032)[0])],
            crop=crop, rtl_rows=slice(crop[0].start, crop[0].start + 16)))
    # ---------------------------------------------------------------------------------------------- D
    s = scenes.scene_d()
    S, _ = de_steps(s["noisy"], 2, gated=True)
    ex.append(Example(
        "D.1", "10 % impulses and dead pixels on fine texture", scenes.scene_d,
        [("float, gated", lambda s: ref.blindspot_gated(s["noisy"])[0])],
        [_de("serial, gated", "exact LMS", "serial", S, 2, passes=3, gated=True, rtl=True),
         _de("df, gated", "delayed LMS", "df", S, 2, passes=3, gated=True, key=True, rtl=True),
         _de("systolic, gated", "delayed LMS", "systolic", S, 2, passes=3, gated=True)],
        baselines=[("median 3x3", "baseline", lambda s: sc.median3x3(s["noisy"])),
                   ("switching median, 0.15", "baseline", lambda s: sc.median3x3(s["noisy"], switch=True, thr=0.15))],
        crop=(slice(150, 310), slice(180, 340)), rtl_rows=slice(150, 278), rtl_cols=slice(180, 308)))
    s = scenes.camera_gaussian()
    S, Sb = de_steps(s["noisy"], 2)
    ex.append(Example(
        "D.2", "Gaussian noise on a photograph (no gate)", scenes.camera_gaussian,
        [("float", lambda s: ref.blindspot_lms(s["noisy"], R=2, hole=0, alpha=0.01, passes=2))],
        [_de("serial", "exact LMS", "serial", S, 2, key=True, rtl=True),
         _de("df", "delayed LMS", "df", S, 2, rtl=True),
         _de("systolic", "delayed LMS", "systolic", S, 2),
         _de(f"rowblock (S = {Sb})", "block LMS", "rowblock", Sb, 2)],
        baselines=[("median 3x3", "baseline", lambda s: sc.median3x3(s["noisy"]))],
        crop=(slice(60, 316), slice(140, 396)), rtl_rows=slice(60, 188), rtl_cols=slice(140, 268)))
    s = scene_d3()
    S, _ = de_steps(s["noisy"], 2, gated=True)
    ex.append(Example(
        "D.3", "20 % salt-and-pepper impulses", scene_d3,
        [("float, gated", lambda s: ref.blindspot_gated(s["noisy"])[0]),
         ("float, the hardware's gate constants and step",
          lambda s, S=S: ref.blindspot_gated(s["noisy"], mu2=2.0 ** -S, rate=2 ** -7, scale=1.5)[0])],
        [_de("serial, gated", "exact LMS", "serial", S, 2, passes=3, gated=True, key=True, rtl=True),
         _de("df, gated", "delayed LMS", "df", S, 2, passes=3, gated=True),
         _de("systolic, gated", "delayed LMS", "systolic", S, 2, passes=3, gated=True)],
        baselines=[("median 3x3", "baseline", lambda s: sc.median3x3(s["noisy"])),
                   ("switching median, 0.15", "baseline", lambda s: sc.median3x3(s["noisy"], switch=True, thr=0.15))],
        crop=(slice(100, 300), slice(150, 350)), rtl_rows=slice(100, 228), rtl_cols=slice(150, 278)))
    # ---------------------------------------------------------------------------------------------- E
    s = scenes.scene_e()
    S, Sb = de_steps(s["noisy"], 5)
    ex.append(Example(
        "E.1", "periodic texture under heavy noise, 11 x 11 window", scenes.scene_e,
        [("float, 11 x 11", lambda s: ref.blindspot_lms(s["noisy"], R=5, hole=0, alpha=0.01, passes=2))],
        [_de("folded", "exact LMS", "folded", S, 5, rtl=True),
         _de("df", "delayed LMS", "df", S, 5, key=True),
         _de("systolic", "delayed LMS", "systolic", S, 5),
         _de(f"rowblock (S = {Sb})", "block LMS", "rowblock", Sb, 5)],
        crop=(slice(160, 352), slice(160, 352)), rtl_rows=slice(160, 256), rtl_cols=slice(160, 256)))
    s = scenes.lattice()
    S, Sb = de_steps(s["noisy"], 4)
    ex.append(Example(
        "E.2", "a two-tone lattice in white noise, 9 x 9 window", scenes.lattice,
        [("float, 9 x 9", lambda s: ref.blindspot_lms(s["noisy"], R=4, hole=0, alpha=0.01, passes=2))],
        [_de("folded", "exact LMS", "folded", S, 4, rtl=True),
         _de("df", "delayed LMS", "df", S, 4, key=True),
         _de("systolic", "delayed LMS", "systolic", S, 4),
         _de(f"rowblock (S = {Sb})", "block LMS", "rowblock", Sb, 4)],
        crop=(slice(0, 192), slice(0, 192)), rtl_rows=slice(48, 144), rtl_cols=slice(48, 144)))
    s = scene_e3()
    S0, _ = de_steps(s["noisy"], 3, 0)
    S1, Sb1 = de_steps(s["noisy"], 3, 1)
    ex.append(Example(
        "E.3", "texture under correlated noise: the blind spot matters", scene_e3,
        [("float, 7 x 7, blind spot 3 x 3",
          lambda s: ref.blindspot_lms(s["noisy"], R=3, hole=1, alpha=0.01, passes=2)),
         ("float, 7 x 7, blind spot 1 x 1",
          lambda s: ref.blindspot_lms(s["noisy"], R=3, hole=0, alpha=0.01, passes=2))],
        [_de("df, blind spot 3 x 3", "delayed LMS", "df", S1, 3, 1, key=True, rtl=True),
         _de("systolic, blind spot 3 x 3", "delayed LMS", "systolic", S1, 3, 1),
         _de(f"rowblock, blind spot 3 x 3 (S = {Sb1})", "block LMS", "rowblock", Sb1, 3, 1),
         _de("df, blind spot 1 x 1", "delayed LMS", "df", S0, 3, 0, rtl=True)],
        crop=(slice(160, 352), slice(160, 352)), rtl_rows=slice(160, 256), rtl_cols=slice(160, 256)))
    # ---------------------------------------------------------------------------------------------- F
    s = scenes.scene_f()

    def f1_float(s):
        w = ref.train_row_weight(s["dark"], s["dark_ob"])
        y1 = s["noisy"] - w * s["ob"].mean(axis=1, keepdims=True)
        return ref.channel_reference_canceller(y1, s["ref"], s["dark"], s["dark_ref"])[0]

    ex.append(Example(
        "F.1", "row banding and readout telegraph on a faint field", scenes.scene_f,
        [("float, both references", f1_float)],
        [Config("OB, dark frame", "exact LMS", "f_ob", dict(S=1), rtl=True),
         Config("OB, online", "exact LMS", "f_online", dict(S=-3), rtl=True),
         Config("OB + channel", "exact LMS", "f_ob_channel", dict(S=1, Sc=f_channel_step(s)), key=True, rtl=True)],
        crop=(slice(250, 442), slice(40, 232)), disp="astro"))
    ex.append(Example(
        "F.2", "row banding with optical-black columns", scene_f2,
        [("float, dark frame", lambda s: s["noisy"] - ref.train_row_weight(s["dark"], s["dark_ob"])
          * s["ob"].mean(axis=1, keepdims=True))],
        [Config("OB, dark frame", "exact LMS", "f_ob", dict(S=1), key=True, rtl=True),
         Config("OB, online", "exact LMS", "f_online", dict(S=-3), rtl=True)],
        crop=(slice(100, 356), slice(200, 456))))
    s = scene_f3()
    ex.append(Example(
        "F.3", "readout telegraph noise with a reference output", scene_f3,
        [("float", lambda s: ref.channel_reference_canceller(s["noisy"], s["ref"], s["dark"], s["dark_ref"])[0])],
        [Config("reference channel, dark frame", "exact LMS", "f_channel", dict(S=f_channel_step(s)), key=True,
                rtl=True)],
        crop=(slice(100, 356), slice(150, 406))))
    return {e.id: e for e in ex}


def select(ids, args):
    """Example ids from command-line arguments: a scenario letter (all three), or an id as A.2 or A2."""
    out = []
    for a in args:
        a = a.upper()
        if len(a) == 1:
            out += [k for k in ids if k[0] == a]
        else:
            out.append(a if "." in a else f"{a[0]}.{a[1:]}")
    bad = [k for k in out if k not in ids]
    if bad:
        raise SystemExit(f"unknown examples {bad}: choose from {list(ids)} or a scenario letter")
    return out


# ----------------------------------------------------------------------------------------------- run
def _a_input(s, kw):
    ar = Arith(S=kw["S"])
    if kw["log"]:
        lg, ex, VMIN, VSTEP = sc.log_luts(0.02)
        codes = lg[np.clip(ar.code(s["noisy"]), 0, len(lg) - 1)]

        def post(v):
            return ar.real(ex[np.clip((v - VMIN) >> VSTEP, 0, len(ex) - 1)])
    else:
        codes = ar.code(s["noisy"])

        def post(v):
            return ar.real(v)
    return ar, codes, post


def _f_frames(s, kw, kind, ar):
    """Frame sequences of scen_f_top: (mode, pixels, OB columns, reference) codes."""
    q = ar.code
    H, W = s["noisy"].shape
    nob = np.zeros((H, 16), np.int64)
    if kind == "f_ob":
        return [(1, q(s["dark"]), q(s["dark_ob"]), None)] * 3 + [(0, q(s["noisy"]), q(s["ob"]), None)], 0
    if kind == "f_online":
        return [(2, q(s["noisy"]), q(s["ob"]), None)], 0
    return [(1, q(s["dark"]), nob, q(s["dark_ref"])), (0, q(s["noisy"]), nob, q(s["ref"]))], 1


def run(e, s, c, impl, ap_types=None):
    """One configuration of one example: (output image, raw output words of the top)."""
    kw, kind = c.kw, c.kind
    work = WORK / f"{e.id.replace('.', '_')}_{c.label.split(' (')[0].replace(', ', '_').replace(' ', '_')}"
    H, W = s["noisy"].shape
    n = H * W
    if kind == "a":
        ar, codes, post = _a_input(s, kw)
        if impl == "model":
            raw = ar.code(sc.scenario_a(ar.real(codes), s["freqs"], S=kw["S"], engine=kw["engine"],
                                        passes=kw["passes"])).ravel()
        else:
            off = int(ar.code(ar.real(codes).mean()))
            raw = hwrun.scen_a(work, codes, s["freqs"], S=kw["S"], engine=kw["engine"], passes=kw["passes"],
                               off=off, impl=impl, ap_types=ap_types)[-n:]
        return post(raw.reshape(H, W)), raw
    if kind == "b":
        ar = Arith(S=max(kw["S"], 0))
        if impl == "model":
            out, track = sc.scenario_b(s["noisy"], S=kw["S"], mode=kw["mode"], sk=kw["sk"], tau=kw["tau"])
            raw = np.stack([ar.code(out).ravel(), ar.code(track).ravel()], 1)
        else:
            raw = hwrun.scen_b(work, ar.code(s["noisy"]), S=kw["S"], mode=kw["mode"], SK=kw["sk"],
                               TAU=int(round(kw["tau"] * 4096)), impl=impl, ap_types=ap_types)
        return ar.real(raw[:, 0].reshape(H, W)), raw
    if kind == "c":
        ar = Arith(S=kw["S"])
        if impl == "model":
            raw = ar.code(sc.scenario_c(s["noisy"], S=kw["S"], engine=kw["engine"])).ravel()
        else:
            raw = hwrun.scen_c(work, ar.code(s["noisy"]), S=kw["S"], L=128, DELAY=8, engine=kw["engine"],
                               impl=impl, ap_types=ap_types)
        return ar.real(raw.reshape(H, W)), raw
    if kind == "de":
        ar = Arith(S=kw["S"])
        gated = kw["gated"]
        if impl == "model":
            r = sc.scenario_de(s["noisy"], S=kw["S"], R=kw["R"], H=kw["H"], engine=kw["engine"],
                               passes=kw["passes"], gated=gated)
            o, fl = r if gated else (r, np.zeros((H, W), bool))
            raw = np.stack([ar.code(o).ravel(), fl.ravel().astype(np.int64)], 1)
        else:
            off = int(ar.code(np.median(s["noisy"]) if gated else s["noisy"].mean()))
            raw = hwrun.scen_de(work, ar.code(s["noisy"]), R=kw["R"], HOLE=kw["H"], S=kw["S"], engine=kw["engine"],
                                passes=kw["passes"], gated=gated, off=off, impl=impl, ap_types=ap_types)[-n:]
        return ar.real(raw[:, 0].reshape(H, W)), raw
    if kind in ("f_ob", "f_online", "f_channel"):
        S = kw["S"]
        ar = Arith(S=S)
        if impl == "model":
            if kind == "f_ob":
                img = sc.scenario_f_row(s["noisy"], s["ob"], s["dark"], s["dark_ob"], S=S)[0]
            elif kind == "f_online":
                img = sc.scenario_f_online(s["noisy"], s["ob"], S=S)[0]
            else:
                img = sc.scenario_f_channel(s["noisy"], s["ref"], s["dark"], s["dark_ref"], S=S)[0]
            raw = ar.code(img).ravel()
        else:
            frames, xsel = _f_frames(s, kw, kind, ar)
            raw = hwrun.scen_f(work, frames, S=S, xsel=xsel, impl=impl, ap_types=ap_types)[-n:]
        return ar.real(raw.reshape(H, W)), raw
    if kind == "f_ob_channel":                       # two tops in series: OB, then the reference channel
        s1 = dict(s)
        img1, raw1 = run(e, s, Config(c.label, c.cls, "f_ob", dict(S=kw["S"])), impl, ap_types)
        s1["noisy"] = img1
        img2, raw2 = run(e, s1, Config(c.label + " 2", c.cls, "f_channel", dict(S=kw["Sc"])), impl, ap_types)
        return img2, np.concatenate([raw1, raw2])
    raise ValueError(kind)


def score(e, x, img):
    x, img = x[:, e.cols], img[:, e.cols]
    if e.aligned:
        return ref.offset_aligned_psnr(x, img), ref.ssim(x, img - np.mean(img - x))
    return ref.psnr(x, img), ref.ssim(x, img)
