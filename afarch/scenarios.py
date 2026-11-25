"""Fixed-point pipelines of the six scenarios: front end + engine + output, exactly as the RTL tops compute them.

Every function takes a float image in [0, 1], works on Q12 codes and returns the output as a float image, so
the result can be scored against the floating-point algorithm (afarch.reference). The engine argument picks
the architecture: "serial", "folded", "df", "systolic", "rowblock" or "da" (see afarch.engines); the
pipelined ones see the same step stream as in the RTL tops (pre-roll shifts and drains included).
"""
import numpy as np

from . import frontends as fe
from .engines import Engine, Gate, ENGINE_CLASS, adaptation_delay, commit_delay
from .fxp import Arith, sat, sgn

PIPELINED = ("df", "systolic", "rowblock")
ENGINE_CLASS_LABEL = {"serial": "exact LMS", "folded": "exact LMS", "df": "delayed LMS", "systolic": "delayed LMS",
                      "rowblock": "block LMS", "da": "block LMS"}


def is_pipelined(name):
    return name in PIPELINED or name.startswith("dlms:")


def make_engine(name, ar, L, out="e", gate=None, A0=None):
    """A named engine, or "dlms:<D>" for a delayed LMS with an arbitrary adaptation delay D."""
    if name.startswith("dlms:"):
        return Engine(ar, L, "dlms", D=int(name[5:]), A=A0, out=out, gate=gate)
    return Engine(ar, L, ENGINE_CLASS[name], D=adaptation_delay(name, L), Dc=commit_delay(name, L),
                  A=A0, out=out, gate=gate)


def default_drain(name, L):
    """Drain steps the RTL tops insert after each row: the row-block commit needs T + 4 of them."""
    return commit_delay(name, L) + 1 if name == "rowblock" else 0


def run_row(eng, name, X, d, p=None, adapt=None, preroll=0, drain=0):
    """One image row through an engine model, with the pipelined engines' pre-roll and drain steps."""
    W, L = X.shape
    if is_pipelined(name) and (preroll or drain):
        n = preroll + W + drain
        Xs = np.zeros((n, L), np.int64)
        Xs[preroll:preroll + W] = X
        pad = lambda v, fill=0: np.concatenate([np.full(preroll, fill), np.asarray(v), np.full(drain, fill)])  # noqa
        valid = pad(np.ones(W, bool), False).astype(bool)
        last = np.zeros(n, bool)
        last[preroll + W - 1] = True
        r = eng.process(Xs, pad(d), p=None if p is None else pad(p), valid=valid, last=last,
                        adapt=None if adapt is None else pad(adapt, False).astype(bool))
    else:
        last = np.zeros(W, bool)
        last[-1] = True
        r = eng.process(X, d, p=p, adapt=adapt, last=last)
    return r


# ------------------------------------------------------------------------------------------------ A
def scenario_a(img, freqs, *, S, engine="serial", passes=2, NA=10, offset=None, record=False, ar=None):
    """A: plane-wave references from a raster phase accumulator and a cosine table; output = error."""
    ar = Arith(S=S) if ar is None else ar
    Hh, Ww = img.shape
    K2 = 2 * len(freqs)
    X = fe.plane_wave_taps(img.shape, freqs, NA).reshape(Hh, Ww, K2)
    pix = ar.code(img)
    off = int(ar.code(img.mean())) if offset is None else int(offset)
    z = pix - off
    eng = make_engine(engine, ar, K2, out="e")
    out = np.empty_like(z)
    hist = []
    for _ in range(passes):
        for r in range(Hh):
            out[r] = run_row(eng, engine, X[r], z[r], drain=default_drain(engine, K2))["out"]
            if record:
                hist.append(ar.weight_real(eng.A))
        eng.finish()
    res = ar.real(sat(out + off, ar.WD))
    return (res, dict(weights=np.array(hist), S=S)) if record else res


def log_luts(eps=0.02, FD=12, NIN=13, VMIN=-16384, VSTEP=2, NOUT=13):
    """ROMs of the log-domain wrapper of A (multiplicative interference): ln(c + eps) in, exp(v) - eps out.

    The log ROM is addressed by the input code (2^NIN entries); the exp ROM by (v - VMIN) >> VSTEP (2^NOUT
    entries), i.e. a log-domain resolution of 2^VSTEP codes. Both hold Q FD codes (one or two RAMB36 each)."""
    c = np.arange(1 << NIN)
    lg = np.round(np.log(c / (1 << FD) + eps) * (1 << FD)).astype(np.int64)
    v = VMIN + (np.arange(1 << NOUT) << VSTEP)
    ex = np.round((np.exp(v / (1 << FD)) - eps) * (1 << FD)).astype(np.int64)
    return lg, sat(ex, 16), VMIN, VSTEP


def scenario_a_log(img, freqs, *, S, engine="serial", passes=3, NA=10, eps=0.02, ar=None):
    """A in the log domain: log ROM -> notch -> exp ROM. Multiplicative bands become additive."""
    ar = Arith(S=S) if ar is None else ar
    lg, ex, VMIN, VSTEP = log_luts(eps)
    c = np.clip(ar.code(img), 0, len(lg) - 1)
    lz = lg[c]
    out = scenario_a(ar.real(lz), freqs, S=S, engine=engine, passes=passes, NA=NA, ar=ar)
    v = ar.code(out)
    idx = np.clip((v - VMIN) >> VSTEP, 0, len(ex) - 1)
    return ar.real(ex[idx])


# ------------------------------------------------------------------------------------------------ B
def bias_run(d, *, S, mode="lms", sk=0, tau=0, rowinit=True, WD=16):
    """B: the one-weight canceller with x = 1 (rtl/scenarios/scen_b_top.v), along one row of codes.

    Bacc has FD + S fractional bits, b = sat(Bacc >>> S), e = sat(d - b), output e.
      lms   : Bacc += e                     (mu = 2^-S)
      sign  : Bacc += sgn(e) << sk          (b moves by 2^(sk - S) codes per pixel)
      gated : Bacc += e only when |e| < tau
    rowinit: the first pixel of the row loads b = d(0).
    """
    d = np.asarray(d, np.int64)
    out = np.empty_like(d)
    track = np.empty_like(d)
    Bacc = int(d[0]) << S if rowinit else 0
    for j, dj in enumerate(d):
        b = sat(Bacc >> S, WD)
        e = sat(int(dj) - b, WD)
        out[j], track[j] = e, b
        if mode == "lms":
            Bacc += e
        elif mode == "sign":
            Bacc += sgn(e) << sk
        elif abs(e) < tau:
            Bacc += e
    return out, track


def scenario_b(img, *, S, mode="lms", sk=0, tau=0.08, FD=12):
    ar = Arith(S=max(S, 0))
    pix = ar.code(img)
    out = np.empty_like(pix)
    track = np.empty_like(pix)
    t = int(round(tau * (1 << FD)))
    for r in range(img.shape[0]):
        out[r], track[r] = bias_run(pix[r], S=S, mode=mode, sk=sk, tau=t)
    return ar.real(out), ar.real(track)


# ------------------------------------------------------------------------------------------------ C
def scenario_c(img, *, S, L=128, delay=8, engine="serial", sigma=4.0, GF=16, record=False, ar=None):
    """C: Gaussian high band per row, reflected delayed-reference taps, output = pixel - predicted interference."""
    ar = Arith(S=S) if ar is None else ar
    kern = fe.gauss_kernel(sigma, 16, GF)
    pix = ar.code(img)
    eng = make_engine(engine, ar, L, out="p-y")
    out = np.empty_like(pix)
    pre = L - 1 if is_pipelined(engine) else 0
    for r in range(img.shape[0]):
        h = fe.highband_row(pix[r], kern, GF)
        X = fe.tdl_taps_row(h, L, delay)
        out[r] = run_row(eng, engine, X, h, p=pix[r], preroll=pre, drain=default_drain(engine, L))["out"]
    eng.finish()
    res = ar.real(out)
    return (res, dict(weights=ar.weight_real(eng.A), S=S)) if record else res


# ---------------------------------------------------------------------------------------------- D / E
def scenario_de(img, *, S, R=2, H=0, engine="serial", passes=2, gated=False, offset=None, record=False,
                gate_kw=None, ar=None):
    """D / E: reflect-padded blind-spot window, output = prediction y (or the gated choice for D)."""
    ar = Arith(S=S) if ar is None else ar
    pix = ar.code(img)
    if offset is None:
        offset = np.median(img) if gated else img.mean()
    off = int(ar.code(offset))
    z = pix - off
    L = len(fe.tap_offsets(R, H))
    gate = Gate(ar, **(gate_kw or {})) if gated else None
    A0 = np.full(L, int(ar.acc_from_weight(1.0 / L))) if gated else None
    eng = make_engine(engine, ar, L, out="gated" if gated else "y", gate=gate, A0=A0)
    src = z.copy()
    out = np.empty_like(z)
    flags = np.zeros(z.shape, bool)
    k = 2 * R + 1
    m = np.zeros((k, k), bool)
    for a, b in fe.tap_offsets(R, H):
        m[a + R, b + R] = True
    mflat = m.ravel()
    for _ in range(passes):
        pad = np.pad(src, R, mode="reflect")
        for r in range(img.shape[0]):
            win = np.lib.stride_tricks.sliding_window_view(pad[r:r + k], (k, k))[0].reshape(img.shape[1], k * k)
            X = np.ascontiguousarray(win[:, mflat])
            res = run_row(eng, engine, X, z[r], drain=default_drain(engine, L))
            out[r] = res["out"]
            flags[r] = res["flag"]
        eng.finish()
        if gated:
            src = out.copy()
    o = ar.real(sat(out + off, ar.WD))
    if record:
        kern = np.zeros(k * k)
        kern[mflat] = ar.weight_real(eng.A)
        return o, dict(weights=kern.reshape(k, k), flags=flags, S=S, L=L)
    return (o, flags) if gated else o


# ------------------------------------------------------------------------------------------------ F
def scenario_f_row(img, ob, dark, dark_ob, *, S, passes=3, log2n=4):
    """F (optical black): train w on a dark frame (d = pixel, x = OB row mean), then subtract w x_ob."""
    ar = Arith(S=S)
    xo = fe.ob_mean(ar.code(dark_ob), log2n)
    dk = ar.code(dark)
    eng = make_engine("serial", ar, 1, out="e")
    Hh, Ww = dark.shape
    for _ in range(passes):
        for r in range(Hh):
            eng.process(np.full((Ww, 1), xo[r]), dk[r])
    w = eng.A.copy()
    xs = fe.ob_mean(ar.code(ob), log2n)
    pix = ar.code(img)
    out = np.empty_like(pix)
    for r in range(Hh):
        out[r] = eng.process(np.full((Ww, 1), xs[r]), pix[r], adapt=np.zeros(Ww, bool))["out"]
    return ar.real(out), ar.weight_real(w)[0]


def scenario_f_online(img, ob, *, S, log2n=4, engine="serial"):
    """F2 (optical black, online, mode 2 of scen_f_top): during the OB readout of every row, adapt on each OB
    pixel with the leave-one-out reference x_k = (sum - ob_k) / (N - 1); then correct the row's scene pixels
    with the frozen weight and the full OB mean. Starts from w = 0 and needs no dark frame."""
    ar = Arith(S=S)
    n = 1 << log2n
    inv = ((1 << ar.FD) + (n - 1) // 2) // (n - 1)
    obc = ar.code(ob)
    pix = ar.code(img)
    L = 1
    eng = make_engine(engine, ar, L, out="e")
    out = np.empty_like(pix)
    Hh, Ww = img.shape
    for r in range(Hh):
        ssum = int(obc[r].sum())
        xl = ((ssum - obc[r]) * inv) >> ar.FD
        eng.process(xl.reshape(-1, 1), obc[r], adapt=np.ones(n, bool))         # as scen_f_top, mode 2
        X = np.full((Ww, 1), ssum >> log2n)
        out[r] = run_row(eng, engine, X, pix[r], adapt=np.zeros(Ww, bool), drain=default_drain(engine, L))["out"]
    eng.finish()
    return ar.real(out), ar.weight_real(eng.A)[0]


def scenario_f_channel(img, ref, dark, dark_ref, *, S):
    """F (reference channel): one tap on the concurrent reference sample, trained on a dark frame, frozen."""
    ar = Arith(S=S)
    eng = make_engine("serial", ar, 1, out="e")
    eng.process(ar.code(dark_ref).reshape(-1, 1), ar.code(dark).ravel())
    pix = ar.code(img).ravel()
    out = eng.process(ar.code(ref).reshape(-1, 1), pix, adapt=np.zeros(pix.size, bool))["out"]
    return ar.real(out).reshape(img.shape), ar.weight_real(eng.A)[0]


# -------------------------------------------------------------------------------------------- baseline
def median3x3(img, *, switch=False, thr=0.1):
    """The baseline of rtl/baselines/median3x3_top.v on Q12 codes: 3 x 3 median with mirrored borders, or the
    switching median that replaces only the pixels farther than thr from the median."""
    from scipy.ndimage import median_filter
    ar = Arith()
    codes = np.clip(ar.code(img), 0, None)
    med = median_filter(codes, size=3, mode="mirror")
    if switch:
        med = np.where(np.abs(codes - med) > int(round(thr * (1 << ar.FD))), med, codes)
    return ar.real(med)
