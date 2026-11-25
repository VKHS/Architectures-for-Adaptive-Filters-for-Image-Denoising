"""The algorithm of every scenario, illustrated: one multi-panel figure per scenario, computed on the models.

    python experiments/algorithms.py            # all six (about 8 minutes)
    python experiments/algorithms.py A E        # some

Writes figures/algorithms/algorithm_<scenario>.png and results/algorithms.json (the numbers quoted in the
chapters: bandwidths, pole radii, Wiener bounds, detection rates, weights).

A  the closed-loop notch and its bandwidth; the poles with an adaptation delay; amplitudes learned by the weights;
   the spectrum before and after; the lattice notch (A4) following a drifting frequency
B  the bias canceller as a first-order high-pass; three tracks along a scan line; a step; robustness to objects
C  the two-band split; why the reference is delayed; the predictor's notch following the stripe frequency; the
   learning curves of the engine classes
D  the learned blind-spot kernel; learning curves; the robust gate at work; detections and false alarms
E  the ALE gain against the window size (exact Wiener bound and LMS); a learned kernel and its frequency response;
   correlated noise and the blind spot
F  the signal model; the weights converging; residual banding against the number of optical-black columns; the
   row-offset profile before and after
"""
import json
import sys

import numpy as np
from scipy.ndimage import gaussian_filter1d, uniform_filter1d

from common import save, RESULTS, Timer
from afarch import scenarios as sc, scenes, reference as ref, frontends as fe, lattice
from afarch.engines import Engine, Gate
from afarch.fxp import Arith
from afarch.plotstyle import (BLUE, ORANGE, AQUA, YELLOW, VIOLET, RED, INK, INK2, MUTED, GRID, clean_axes,
                              panel_label)
import example_defs as xd

import matplotlib.pyplot as plt                                  # noqa: E402  (after the style setup)

NUM = {}


def figure(nrows, ncols, w=15.5, h=8.6, **kw):
    fig, axs = plt.subplots(nrows, ncols, figsize=(w, h), squeeze=False, **kw)
    return fig, axs


def label_all(axs):
    for k, ax in enumerate(np.ravel(axs)):
        if ax.get_visible():
            panel_label(ax, f"({'abcdefghij'[k]})", x=-0.04, y=1.03)


def spectrum(img):
    """Log magnitude of the centred 2-D spectrum (mean removed, Hann window)."""
    z = img - img.mean()
    wi = np.hanning(z.shape[0])[:, None] * np.hanning(z.shape[1])[None, :]
    return 20 * np.log10(np.abs(np.fft.fftshift(np.fft.fft2(z * wi))) + 1e-3)


def kernel_panel(ax, k, title, hole=0, fmt="{:+.2f}", annotate=True, vmax=None):
    R = k.shape[0] // 2
    v = vmax or max(1e-6, float(np.abs(k).max()))
    ax.imshow(k, cmap="RdBu_r", vmin=-v, vmax=v, interpolation="nearest")
    for a in range(k.shape[0]):
        for b in range(k.shape[1]):
            if max(abs(a - R), abs(b - R)) <= hole:
                ax.add_patch(plt.Rectangle((b - 0.5, a - 0.5), 1, 1, facecolor="#d9d8d2", edgecolor="none"))
            elif annotate:
                ax.text(b, a, fmt.format(k[a, b]), ha="center", va="center", fontsize=6.5,
                        color="white" if abs(k[a, b]) > 0.6 * v else INK)
    ax.set_xticks([])
    ax.set_yticks([])
    for sp in ax.spines.values():
        sp.set_visible(False)
    ax.set_title(title, fontsize=9)


# ================================================================================================== A
def figure_a():
    fig, axs = figure(2, 3)
    # (a) Glover's notch for several mu C^2
    f0 = 0.1
    w0 = 2 * np.pi * f0
    f = np.linspace(0.08, 0.12, 8001)
    z = np.exp(1j * 2 * np.pi * f)
    ax = axs[0, 0]
    bw = {}
    for m, col in ((0.003, BLUE), (0.01, ORANGE), (0.03, AQUA)):
        H = (z ** 2 - 2 * z * np.cos(w0) + 1) / (z ** 2 - (2 - m) * z * np.cos(w0) + 1 - m)
        g = 20 * np.log10(np.abs(H) + 1e-9)
        ax.plot(f, g, color=col, lw=1.8, label=f"$\\mu C^2$ = {m}")
        ff = np.linspace(f0 - 0.02, f0 + 0.02, 400001)          # the -3 dB width on a fine grid
        zz = np.exp(1j * 2 * np.pi * ff)
        gg = np.abs((zz ** 2 - 2 * zz * np.cos(w0) + 1) / (zz ** 2 - (2 - m) * zz * np.cos(w0) + 1 - m))
        below = ff[gg < 2 ** -0.5]
        bw[m] = float(below.max() - below.min()) if len(below) else 0.0
    ax.set_xlim(0.085, 0.115)
    ax.set_ylim(-40, 3)
    ax.set_xlabel("frequency (cycles/sample)")
    ax.set_ylabel("|H| (dB)")
    ax.set_title("closed loop from d to e: a notch at $\\omega_0$")
    ax.legend(loc="lower left")
    clean_axes(ax, grid_x=True)
    NUM["A_bandwidth_cycles"] = {str(k): round(v, 5) for k, v in bw.items()}
    NUM["A_bandwidth_predicted"] = {str(m): round(m / (2 * np.pi), 5) for m in bw}
    # (b) poles with an adaptation delay D
    ax = axs[0, 1]
    m = 0.01
    t = np.linspace(0, 2 * np.pi, 400)
    ax.plot(np.cos(t), np.sin(t), color=GRID, lw=1.0)
    radii = {}
    for D, col, mk in ((0, BLUE, "x"), (5, ORANGE, "+"), (27, AQUA, "1")):
        # denominator z^D (z^2 - 2 z cos w0 + 1) + m (z cos((D+1) w0) - cos(D w0))
        p1 = np.zeros(D + 3)
        p1[:3] = [1, -2 * np.cos(w0), 1]
        p2 = np.zeros(D + 3)
        p2[-2:] = [m * np.cos((D + 1) * w0), -m * np.cos(D * w0)]
        poles = np.roots(p1 + p2)
        ax.plot(poles.real, poles.imag, mk, color=col, ms=8, mew=1.6, label=f"poles, D = {D}")
        near = poles[np.argsort(np.abs(np.abs(np.angle(poles)) - w0))[:2]]
        rest = np.setdiff1d(poles, near)
        radii[D] = dict(notch=round(float(np.abs(near).mean()), 5),
                        extra_max=round(float(np.abs(rest).max()), 3) if len(rest) else 0.0)
    ax.plot(np.cos([w0, -w0]), np.sin([w0, -w0]), "o", mfc="none", mec=INK, ms=9, mew=1.4, label="zeros")
    ax.set_aspect("equal")
    ax.set_xlim(-1.15, 1.15)
    ax.set_ylim(-1.15, 1.15)
    ax.set_title(f"poles with a delay D ($\\mu C^2$ = {m})")
    ax.legend(loc="lower left", fontsize=7)
    ax.set_xticks([-1, 0, 1])
    ax.set_yticks([-1, 0, 1])
    NUM["A_pole_radii_mu0.01"] = radii
    # (c) A2: the weights learn the amplitude of every plane wave
    s = scenes.camera_periodic()
    res, info = sc.scenario_a(s["noisy"], s["freqs"], S=12, engine="df", passes=2, record=True)
    wts = info["weights"]
    ax = axs[0, 2]
    amps = (0.10, 0.04, 0.06)
    for k, col in enumerate((BLUE, ORANGE, AQUA)):
        a = np.hypot(wts[:, 2 * k], wts[:, 2 * k + 1])
        ax.plot(np.arange(len(a)), a, color=col, lw=1.6, label=f"wave {k + 1}: (u, v) = {s['freqs'][k]}")
        ax.axhline(amps[k], color=col, lw=0.9, ls="--")
    ax.axvline(512, color=MUTED, lw=0.8, ls=":")
    ax.text(515, 0.112, "second pass", fontsize=7, color=MUTED)
    ax.set_xlim(0, 1024)
    ax.set_ylim(0, 0.12)
    ax.set_xlabel("row (two passes over the frame)")
    ax.set_ylabel("$\\sqrt{w_c^2 + w_s^2}$")
    ax.set_title("A.2: the weights learn the amplitudes (df)")
    ax.legend(fontsize=7, loc="lower right")
    clean_axes(ax)
    NUM["A.2_final_amplitudes"] = [round(float(np.hypot(wts[-1, 2 * k], wts[-1, 2 * k + 1])), 4) for k in range(3)]
    # (d, e) spectra before and after
    for ax, img, title in ((axs[1, 0], s["noisy"], "A.2 corrupted: spectrum"),
                           (axs[1, 1], res, "A.2 after the notch (df): spectrum")):
        sp = spectrum(img)
        ax.imshow(sp, cmap="magma", vmin=sp.max() - 90, vmax=sp.max(), extent=(-0.5, 0.5, 0.5, -0.5))
        for u, v in s["freqs"]:
            for sg in (1, -1):
                uu, vv = ((sg * u + 0.5) % 1) - 0.5, ((sg * v + 0.5) % 1) - 0.5
                ax.add_patch(plt.Circle((vv, uu), 0.03, fill=False, ec=AQUA, lw=1.2))
        ax.set_xlabel("v (cycles/pixel, along a row)")
        ax.set_ylabel("u (cycles/row)")
        ax.set_title(title)
    # (f) A4 on C1: the lattice notch finds and follows a drifting frequency
    s = scenes.scene_c()
    out, ks = lattice.notch_image(s["noisy"], k1=0.9, mu=0.032)
    H = s["noisy"].shape[0]
    ftrue = 0.08 + 0.04 * np.arange(H) / H
    fest = np.arccos(np.clip(-ks, -1, 1)) / (2 * np.pi)
    ax = axs[1, 2]
    ax.plot(np.arange(H), ftrue, color=INK2, lw=1.2, ls="--", label="stripe frequency")
    ax.plot(np.arange(H), fest, color=VIOLET, lw=1.6, label="notch of A4, $\\arccos(-k_0)/2\\pi$")
    ax.set_xlabel("row of example C.1")
    ax.set_ylabel("cycles/pixel")
    ax.set_ylim(0.06, 0.26)
    ax.set_title("A4: one coefficient finds the frequency itself")
    ax.legend(fontsize=7.5)
    clean_axes(ax)
    lock = int(np.argmax(np.abs(fest - ftrue) < 0.002))
    NUM["A4_lock_row"] = lock
    NUM["A4_mean_abs_error_after_lock"] = round(float(np.abs(fest - ftrue)[lock:].mean()), 5)
    label_all(axs)
    fig.subplots_adjust(wspace=0.32, hspace=0.36)
    save(fig, "algorithms", "algorithm_A.png")


# ================================================================================================== B
def figure_b():
    fig, axs = figure(2, 2, w=13.5, h=8.4)
    # (a) the LMS bias canceller is a first-order high-pass
    f = np.logspace(-4, np.log10(0.5), 600)
    z = np.exp(1j * 2 * np.pi * f)
    ax = axs[0, 0]
    for S, col in ((4, BLUE), (6, ORANGE), (8, AQUA)):
        mu = 2.0 ** -S
        Hh = (1 - 1 / z) / (1 - (1 - mu) / z)
        ax.semilogx(f, 20 * np.log10(np.abs(Hh)), color=col, lw=1.8, label=f"S = {S}: corner {mu / (2 * np.pi):.4f}")
        ax.axvline(mu / (2 * np.pi), color=col, lw=0.8, ls=":")
    ax.set_ylim(-40, 3)
    ax.set_xlabel("frequency along the row (cycles/pixel)")
    ax.set_ylabel("|E/D| (dB)")
    ax.set_title("LMS update: $E/D=(1-z^{-1})/(1-(1-\\mu)z^{-1})$")
    ax.legend(fontsize=7.5, loc="lower right")
    clean_axes(ax, grid_x=True)
    # (b) three tracks along one scan line of B1
    s = scenes.scene_b()
    ar = Arith(S=6)
    r = 300
    d = ar.code(s["noisy"][r])
    j = np.arange(d.size)
    ax = axs[0, 1]
    ax.plot(j, s["noisy"][r], color="#b9b8b0", lw=0.8, label="scan line d")
    ax.plot(j, 0.3 + s["bias"][r], color=INK, lw=1.2, ls="--", label="background + bias (truth)")
    for mode, S, sk, col, lab in (("lms", 6, 0, RED, "LMS, S = 6"), ("sign", 4, 6, ORANGE, "sign-error, S = 4"),
                                  ("gated", 4, 0, BLUE, "gated, S = 4")):
        _, tr = sc.bias_run(d, S=S, mode=mode, sk=sk, tau=int(0.08 * 4096))
        ax.plot(j, tr / 4096.0, color=col, lw=1.5, label=lab)
    ax.set_xlabel("pixel along row 300 of B.1")
    ax.set_ylabel("height")
    ax.set_title("the bias track b of the three updates")
    ax.legend(fontsize=7, loc="upper left", ncol=2)
    clean_axes(ax)
    # (c) a step in the bias
    rng = np.random.default_rng(3)
    n = 512
    true = 0.3 + 0.2 * (np.arange(n) >= 200)
    d = ar.code(true + 0.01 * rng.standard_normal(n))
    ax = axs[1, 0]
    ax.plot(np.arange(n), true, color=INK, lw=1.2, ls="--", label="bias (truth)")
    for mode, S, sk, col, lab in (("lms", 4, 0, VIOLET, "LMS, S = 4"), ("lms", 6, 0, RED, "LMS, S = 6"),
                                  ("sign", 4, 6, ORANGE, "sign-error, S = 4, SK = 6"),
                                  ("gated", 4, 0, BLUE, "gated, $\\tau$ = 0.08")):
        _, tr = sc.bias_run(d, S=S, mode=mode, sk=sk, tau=int(0.08 * 4096))
        ax.plot(np.arange(n), tr / 4096.0, color=col, lw=1.5, label=lab)
    ax.set_xlim(150, 512)
    ax.set_xlabel("pixel")
    ax.set_ylabel("bias track")
    ax.set_title("a step of 0.2 (a tip change): time constant, slew, lock-out")
    ax.legend(fontsize=7, loc="center right")
    clean_axes(ax)
    # (d) error of the track against the share of the row covered by objects
    cover, err = {}, {}
    modes = (("lms", 6, 0, RED, "LMS"), ("sign", 4, 6, ORANGE, "sign-error"), ("gated", 4, 0, BLUE, "gated"))
    rng = np.random.default_rng(11)
    W = 512
    jj = np.arange(W)
    for nobj in (0, 2, 4, 8, 12, 16, 24, 32):
        cs, es = [], {m[0]: [] for m in modes}
        for _ in range(60):
            bias = 0.05 * np.sin(2 * np.pi * rng.uniform(0.5, 1.2) * jj / W + 2 * np.pi * rng.random()) \
                + 0.05 * rng.standard_normal()
            obj = np.zeros(W)
            for _ in range(nobj):
                c = rng.uniform(24, W - 8)
                obj += rng.uniform(0.25, 0.5) * np.exp(-(jj - c) ** 2 / (2 * rng.uniform(3, 8) ** 2))
            cs.append(float((obj > 0.05).mean()))
            dd = ar.code(0.3 + bias + obj + 0.01 * rng.standard_normal(W))
            for mode, S, sk, _, _ in modes:
                _, tr = sc.bias_run(dd, S=S, mode=mode, sk=sk, tau=int(0.08 * 4096))
                es[mode].append(np.sqrt(np.mean((tr[32:] / 4096.0 - 0.3 - bias[32:]) ** 2)))
        cover[nobj] = float(np.mean(cs))
        for m in es:
            err.setdefault(m, []).append(float(np.mean(es[m])))
    ax = axs[1, 1]
    xs = [cover[k] for k in sorted(cover)]
    for mode, _, _, col, lab in modes:
        ax.plot(np.array(xs) * 100, np.array(err[mode]) * 4096, "o-", color=col, lw=1.6, ms=4, label=lab)
    ax.set_xlabel("share of the row covered by objects (%)")
    ax.set_ylabel("RMS error of the track (LSB of Q12)")
    ax.set_yscale("log")
    ax.set_title("objects pull LMS most, the sign-error update less, the gate least")
    ax.legend(fontsize=7.5)
    clean_axes(ax)
    NUM["B_track_rms_lsb"] = {m: [round(v * 4096, 1) for v in err[m]] for m in err}
    NUM["B_coverage_percent"] = [round(c * 100, 1) for c in xs]
    label_all(axs)
    fig.subplots_adjust(wspace=0.26, hspace=0.38)
    save(fig, "algorithms", "algorithm_B.png")


# ================================================================================================== C
def c_run(y, S, engine, L=128, delay=8):
    """scenario_c with the weights recorded after every row."""
    ar = Arith(S=S)
    kern = fe.gauss_kernel(4.0, 16, 16)
    pix = ar.code(y)
    eng = sc.make_engine(engine, ar, L, out="p-y")
    pre = L - 1 if sc.is_pipelined(engine) else 0
    out = np.empty_like(pix)
    wts = []
    for r in range(y.shape[0]):
        h = fe.highband_row(pix[r], kern, 16)
        X = fe.tdl_taps_row(h, L, delay)
        out[r] = sc.run_row(eng, engine, X, h, p=pix[r], preroll=pre, drain=sc.default_drain(engine, L))["out"]
        wts.append(ar.weight_real(eng.A))
    return ar.real(out), np.array(wts)


def figure_c():
    fig, axs = figure(2, 2, w=13.5, h=8.6)
    s = scenes.scene_c()
    x, y = s["clean"], s["noisy"]
    H, W = y.shape
    # (a) the two-band split
    ax = axs[0, 0]
    f = np.fft.rfftfreq(4096)
    kern = fe.gauss_kernel(4.0, 16, 16) / 65536.0
    G = np.abs(np.fft.rfft(kern, 4096))
    zc = x - x.mean(axis=1, keepdims=True)
    P = np.mean(np.abs(np.fft.rfft(zc * np.hanning(W)[None, :], 4096, axis=1)) ** 2, axis=0)
    ax.semilogy(f, P / P.max(), color="#b9b8b0", lw=1.0, label="row spectrum of the clean image")
    ax2 = ax.twinx()
    ax2.plot(f, G, color=BLUE, lw=1.8, label="low band G")
    ax2.plot(f, 1 - G, color=ORANGE, lw=1.8, label="high band 1 - G")
    ax2.axvspan(0.08, 0.12, color=YELLOW, alpha=0.25, lw=0)
    ax2.text(0.1, 1.04, "stripes", ha="center", fontsize=7.5, color=INK2)
    ax2.set_ylim(0, 1.12)
    ax2.set_ylabel("gain")
    ax.set_ylabel("power (normalised)")
    ax.set_xlabel("frequency along the row (cycles/pixel)")
    ax.set_xlim(0, 0.5)
    ax.set_title("the split: Gaussian low band ($\\sigma$ = 4) and its complement")
    h1, l1 = ax.get_legend_handles_labels()
    h2, l2 = ax2.get_legend_handles_labels()
    ax2.legend(h1 + h2, l1 + l2, fontsize=7, loc="center right")
    for sp in ("top",):
        ax.spines[sp].set_visible(False)
        ax2.spines[sp].set_visible(False)
    # (b) autocorrelation along rows: the image's high band forgets, the stripes do not
    ax = axs[0, 1]
    hb_img = zc - gaussian_filter1d(zc, 4.0, axis=1, mode="reflect")
    st = y - x
    stc = st - st.mean(axis=1, keepdims=True)
    hb_st = stc - gaussian_filter1d(stc, 4.0, axis=1, mode="reflect")
    lags = np.arange(0, 41)

    def acf(a):
        a = a - a.mean(axis=1, keepdims=True)
        v = np.array([np.mean(a[:, :W - k] * a[:, k:]) for k in lags])
        return v / v[0]

    ax.plot(lags, acf(hb_img), "o-", color=BLUE, lw=1.4, ms=3, label="high band of the image")
    ax.plot(lags, acf(hb_st), "o-", color=ORANGE, lw=1.4, ms=3, label="high band of the stripes")
    ax.axvspan(8, 8 + 128, color=AQUA, alpha=0.12, lw=0)
    ax.text(9, -0.85, "taps: lags 8 .. 135", fontsize=7.5, color=INK2)
    ax.axhline(0, color=GRID, lw=0.8)
    ax.set_xlim(0, 40)
    ax.set_xlabel("lag along the row (pixels)")
    ax.set_ylabel("autocorrelation")
    ax.set_title("why the reference is delayed by 8 pixels")
    ax.legend(fontsize=7.5)
    clean_axes(ax)
    NUM["C_image_highband_acf_lag8"] = round(float(acf(hb_img)[8]), 3)
    # (c) the predictor's notch follows the stripe frequency
    S, Sb = xd.c_steps(y)
    out, wts = c_run(y, S, "serial")
    nf = 512
    freqs = np.arange(nf // 2 + 1) / nf
    Hp = np.fft.rfft(wts, nf, axis=1) * np.exp(-1j * 2 * np.pi * freqs * 8)[None, :]
    notch = 20 * np.log10(np.abs(1 - Hp) + 1e-6)
    ax = axs[1, 0]
    im = ax.imshow(notch, aspect="auto", cmap="viridis", vmin=-30, vmax=6, extent=(0, 0.5, H, 0))
    ax.plot(0.08 + 0.04 * np.arange(H) / H, np.arange(H), color=RED, lw=1.0, ls="--")
    ax.set_xlim(0, 0.3)
    ax.set_xlabel("frequency along the row (cycles/pixel)")
    ax.set_ylabel("row")
    ax.set_title("$|1 - W(e^{j\\omega})e^{-8j\\omega}|$ per row (serial): the notch tracks (red: truth)")
    cb = fig.colorbar(im, ax=ax, fraction=0.04, pad=0.02)
    cb.set_label("dB", fontsize=8)
    # (d) what is left of the stripes: at the start of each row (reflected history) and after it
    ax = axs[1, 1]
    stripes = y - x
    head, tail = slice(0, 136), slice(160, W)

    def share(o, cols):                 # the share of the row's stripe waveform left in the output
        return np.abs(np.sum(((o - x) * stripes)[:, cols], axis=1)) / np.sum((stripes ** 2)[:, cols], axis=1)

    curves = {}
    for eng, SS, col, lab in (("serial", S, BLUE, "exact (serial)"), ("df", S, ORANGE, "delayed (df)"),
                              ("systolic", S, YELLOW, "delayed (systolic)"),
                              ("rowblock", Sb, AQUA, f"block (rowblock, S = {Sb})")):
        o = out if eng == "serial" else sc.scenario_c(y, S=SS, engine=eng)
        curves[eng] = share(o, tail)
        ax.semilogy(np.arange(H), uniform_filter1d(curves[eng], 3), color=col, lw=1.4,
                    label=lab + ", pixels 160-511")
    hs = share(out, head)
    ax.semilogy(np.arange(H), uniform_filter1d(hs, 3), color=VIOLET, lw=1.2, ls=":",
                label="exact (serial), pixels 0-135")
    fi = 0.08 + 0.04 * np.arange(H) / H
    gk = fe.gauss_kernel(4.0, 16, 16) / 65536.0
    Gf = np.abs(np.sum(gk[None, :] * np.cos(2 * np.pi * fi[:, None] * (np.arange(33) - 16)[None, :]), axis=1))
    ax.semilogy(np.arange(H), Gf, color=INK2, lw=1.2, ls="--", label="G(f): the stripes' share in the low band")
    ax.set_xlabel("row")
    ax.set_ylabel("share of the stripes left")
    ax.set_ylim(1e-3, 3)
    ax.set_title("what is left depends on the stripes' phase where a row starts")
    ax.legend(fontsize=6.8, loc="upper right", ncol=2)
    clean_axes(ax)
    NUM["C.1_stripe_share_left_tail_median"] = {k: round(float(np.median(v)), 4) for k, v in curves.items()}
    NUM["C.1_stripe_share_left_head_median"] = round(float(np.median(hs)), 4)
    label_all(axs)
    fig.subplots_adjust(wspace=0.3, hspace=0.38)
    save(fig, "algorithms", "algorithm_C.png")


# ================================================================================================== D
def de_errors(y, S, R, H, engine, passes=1):
    """scenario_de (no gate) with the error of every step returned."""
    ar = Arith(S=S)
    pix = ar.code(y)
    off = int(ar.code(y.mean()))
    z = pix - off
    L = len(fe.tap_offsets(R, H))
    eng = sc.make_engine(engine, ar, L, out="y")
    k = 2 * R + 1
    m = np.zeros((k, k), bool)
    for a, b in fe.tap_offsets(R, H):
        m[a + R, b + R] = True
    es = []
    for _ in range(passes):
        pad = np.pad(z, R, mode="reflect")
        for r in range(y.shape[0]):
            win = np.lib.stride_tricks.sliding_window_view(pad[r:r + k], (k, k))[0].reshape(y.shape[1], k * k)
            res = sc.run_row(eng, engine, np.ascontiguousarray(win[:, m.ravel()]), z[r],
                             drain=sc.default_drain(engine, L))
            es.append(res["e"])
        eng.finish()
    kern = np.zeros(k * k)
    kern[m.ravel()] = ar.weight_real(eng.A)
    return ar.real(np.concatenate(es)), kern.reshape(k, k)


def figure_d():
    fig, axs = figure(2, 2, w=13.0, h=10.0)
    s = scenes.camera_gaussian()
    y = s["noisy"]
    S, Sb = xd.de_steps(y, 2)
    sigma = 20 / 255
    # (a) the learned kernel (D2, serial)
    e_serial, kern = de_errors(y, S, 2, 0, "serial", passes=2)
    kernel_panel(axs[0, 0], kern, f"D.2: the learned 5 x 5 predictor (serial, $\\mu = 2^{{-{S}}}$)\n"
                                  f"sum of the weights {kern.sum():.3f}; the centre is the blind spot")
    NUM["D.2_kernel_sum"] = round(float(kern.sum()), 4)
    # (b) learning curves: the first 24 rows (12 288 pixels) from zero weights
    ax = axs[0, 1]
    npx = 24 * 512
    for eng, SS, col, lab in (("serial", S, BLUE, "exact (serial)"), ("df", S, ORANGE, "delayed (df, D = 8)"),
                              ("systolic", S, YELLOW, "delayed (systolic, D = 27)"),
                              ("rowblock", Sb, AQUA, f"block (rowblock, S = {Sb})")):
        e = e_serial if eng == "serial" else de_errors(y, SS, 2, 0, eng, passes=1)[0]
        ms = uniform_filter1d(e[:npx] ** 2, 256)
        ax.plot(np.arange(npx), 10 * np.log10(ms / sigma ** 2), color=col, lw=1.4, label=lab)
    ax.axhline(0, color=INK2, lw=0.9, ls="--", label="noise power $\\sigma^2$")
    ax.set_xlim(0, npx)
    ax.set_xlabel("pixel (first 24 rows of the first pass)")
    ax.set_ylabel("$E[e^2]/\\sigma^2$ (dB, 256-pixel mean)")
    ax.set_title("learning from zero weights")
    ax.legend(fontsize=7.5)
    clean_axes(ax)
    # (c) the gate at work: D.1, three rows of the third pass (serial engine)
    s1 = scenes.scene_d()
    y1 = s1["noisy"]
    S1, _ = xd.de_steps(y1, 2, gated=True)
    ar = Arith(S=S1)
    z = ar.code(y1) - int(ar.code(np.median(y1)))
    L = 24
    Hh, Ww = y1.shape
    gate = Gate(ar)
    eng = Engine(ar, L, "lms", A=np.full(L, int(ar.acc_from_weight(1.0 / L))), out="gated", gate=gate)
    src = z.copy()
    out = np.empty_like(z)
    r0, nrows, passes = 100, 3, 3
    es, th, fl = [], [], []
    for p in range(passes):
        X = fe.window_taps(src, 2, 0).reshape(Hh, Ww, L)
        for r in range(Hh):
            if p == passes - 1 and r0 <= r < r0 + nrows:
                for c in range(Ww):
                    th.append(gate.threshold())
                    res = eng.process(X[r, c:c + 1], z[r, c:c + 1])
                    out[r, c] = res["out"][0]
                    es.append(int(res["e"][0]))
                    fl.append(bool(res["flag"][0]))
            else:
                out[r] = eng.process(X[r], z[r])["out"]
        eng.finish()
        src = out.copy()
    es, th, fl = np.array(es) / 4096.0, np.array(th) / 4096.0, np.array(fl)
    truth = s1["corrupted"][r0:r0 + nrows].ravel()
    dev = np.abs(y1 - s1["clean"])[r0:r0 + nrows].ravel()
    ax = axs[1, 0]
    t = np.arange(len(es))
    ax.plot(t, np.abs(es), color="#b9b8b0", lw=0.7, label="|e|")
    ax.plot(t, th, color=BLUE, lw=1.6, label="threshold max(4 s, 0.1)")
    ax.plot(t[fl & truth], np.abs(es)[fl & truth], "o", color=AQUA, ms=3, label="flagged, corrupted")
    ax.plot(t[fl & ~truth], np.abs(es)[fl & ~truth], "o", color=RED, ms=4, label="flagged, clean")
    ax.plot(t[~fl & truth], np.abs(es)[~fl & truth], "x", color=ORANGE, ms=4, label="missed")
    ax.set_xlim(0, len(es))
    ax.set_ylim(0, max(0.8, float(np.abs(es).max()) * 1.05))
    ax.set_xlabel(f"pixel (rows {r0}-{r0 + nrows - 1} of D.1, third pass)")
    ax.set_ylabel("|prediction error|")
    ax.set_title("the robust gate: s follows the errors of clean pixels")
    ax.legend(fontsize=7, ncol=3, loc="upper center")
    clean_axes(ax)
    NUM["D.1_trace_missed_max_deviation"] = round(float(dev[~fl & truth].max()), 3) if (~fl & truth).any() else 0.0
    # (d) detections over the frame (D1, serial, three passes)
    o, flags = sc.scenario_de(y1, S=S1, R=2, passes=3, gated=True, engine="serial")
    tr = s1["corrupted"]
    det = float((flags & tr).sum() / tr.sum())
    fa = float((flags & ~tr).sum() / (~tr).sum())
    vis = tr & (np.abs(y1 - s1["clean"]) > 0.15)
    detv = float((flags & vis).sum() / vis.sum())
    NUM["D.1_detection"] = round(det, 4)
    NUM["D.1_detection_deviation_over_0.15"] = round(detv, 4)
    NUM["D.1_false_alarm"] = round(fa, 5)
    s3 = xd.scene_d3()                                   # D.3: salt and pepper, the same detector
    S3, _ = xd.de_steps(s3["noisy"], 2, gated=True)
    _, fl3 = sc.scenario_de(s3["noisy"], S=S3, R=2, passes=3, gated=True, engine="serial")
    t3 = s3["corrupted"]
    NUM["D.3_detection"] = round(float((fl3 & t3).sum() / t3.sum()), 4)
    NUM["D.3_false_alarm"] = round(float((fl3 & ~t3).sum() / (~t3).sum()), 5)
    cr = (slice(150, 278), slice(180, 308))
    rgb = np.dstack([s1["clean"][cr]] * 3) * 0.55 + 0.25
    rgb[(flags & tr)[cr]] = np.array([0x1b, 0xaf, 0x7a]) / 255
    rgb[(~flags & tr)[cr]] = np.array([0xeb, 0x68, 0x34]) / 255
    rgb[(flags & ~tr)[cr]] = np.array([0xe3, 0x49, 0x48]) / 255
    ax = axs[1, 1]
    ax.imshow(rgb, interpolation="nearest")
    ax.set_xticks([])
    ax.set_yticks([])
    for sp in ax.spines.values():
        sp.set_visible(False)
    ax.set_title(f"D.1 after 3 passes: detected (green) {det * 100:.1f} %,\n"
                 f"{detv * 100:.1f} % of the impulses off by > 0.15; missed (orange);\n"
                 f"false alarms (red) {fa * 100:.2f} % of clean pixels", fontsize=8.5)
    label_all(axs)
    fig.subplots_adjust(wspace=0.22, hspace=0.32)
    save(fig, "algorithms", "algorithm_D.png")


# ================================================================================================== E
def lattice_wiener(R, H, sigma=0.2):
    """Exact Wiener MSE of the blind-spot predictor on the lattice of scenes.lattice (signal autocorrelation
    known in closed form, white noise sigma)."""
    offs = np.array(fe.tap_offsets(R, H), float)

    def rs(di, dj):
        return sum(A * A / 2 * np.cos(2 * np.pi * (u * di + v * dj)) for A, u, v, _ in scenes.LATTICE)

    Rm = rs(offs[:, None, 0] - offs[None, :, 0], offs[:, None, 1] - offs[None, :, 1]) + sigma ** 2 * np.eye(len(offs))
    p = rs(offs[:, 0], offs[:, 1])
    P = rs(0.0, 0.0)
    return float(P - p @ np.linalg.solve(Rm, p))


def figure_e():
    fig = plt.figure(figsize=(15.5, 8.8))
    gs = fig.add_gridspec(2, 4, width_ratios=[1.25, 1, 1, 1], wspace=0.28, hspace=0.36)
    # (a) ALE gain against the window
    s = scenes.lattice()
    x, y = s["clean"], s["noisy"]
    Ls, wien, approx, lms = [], [], [], []
    comps = [(A * A / 4) for A, _, _, _ in scenes.LATTICE for _ in (0, 1)]
    for R in (1, 2, 3, 4, 5):
        L = (2 * R + 1) ** 2 - 1
        S, _ = xd.de_steps(y, R)
        o = sc.scenario_de(y, S=S, R=R, passes=2, engine="df")
        Ls.append(L)
        wien.append(-10 * np.log10(lattice_wiener(R, 0)))
        approx.append(-10 * np.log10(sum(0.04 / (L + 0.04 / P) for P in comps)))
        lms.append(ref.psnr(x, o))
    ax = fig.add_subplot(gs[0, 0])
    ax.plot(Ls, wien, "o-", color=INK2, lw=1.6, ms=4, label="Wiener bound (exact, 2-D window)")
    ax.plot(Ls, approx, "--", color=MUTED, lw=1.2, label="$\\sum_k \\sigma^2/(L+1/\\alpha_k)$")
    ax.plot(Ls, lms, "o-", color=ORANGE, lw=1.8, ms=5, label="LMS, df engine (model)")
    ax.axhline(ref.psnr(x, y), color="#b9b8b0", lw=1.0)
    ax.text(10, ref.psnr(x, y) + 0.3, "corrupted", fontsize=7.5, color=MUTED)
    ax.set_xlabel("taps L = (2R+1)$^2$ - 1")
    ax.set_ylabel("PSNR (dB)")
    ax.set_title("E.2: the ALE gains with the window")
    ax.legend(fontsize=7, loc="upper left")
    clean_axes(ax)
    NUM["E.2_L"] = Ls
    NUM["E.2_wiener_psnr"] = [round(v, 2) for v in wien]
    NUM["E.2_approx_psnr"] = [round(v, 2) for v in approx]
    NUM["E.2_lms_psnr"] = [round(v, 2) for v in lms]
    # (b, c) E1: the learned 11 x 11 kernel and its frequency response
    s = scenes.scene_e()
    S, _ = xd.de_steps(s["noisy"], 5)
    o, info = sc.scenario_de(s["noisy"], S=S, R=5, passes=2, engine="df", record=True)
    k = info["weights"]
    ax = fig.add_subplot(gs[0, 1])
    kernel_panel(ax, k, "E.1: learned 11 x 11 kernel", annotate=False)
    ax = fig.add_subplot(gs[0, 2])
    Wf = np.abs(np.fft.fftshift(np.fft.fft2(k, (128, 128))))
    ax.imshow(Wf, cmap="viridis", extent=(-0.5, 0.5, 0.5, -0.5))
    ax.set_xlabel("v (cycles/pixel)")
    ax.set_ylabel("u (cycles/row)")
    ax.set_title("|W| of the kernel (b)")
    ax = fig.add_subplot(gs[0, 3])
    sp = spectrum(s["clean"])
    ax.imshow(sp, cmap="magma", vmin=sp.max() - 80, vmax=sp.max(), extent=(-0.5, 0.5, 0.5, -0.5))
    ax.set_xlabel("v (cycles/pixel)")
    ax.set_ylabel("u (cycles/row)")
    ax.set_title("spectrum of the clean texture")
    # (d, e, f) E3: correlated noise and the blind spot
    s = xd.scene_e3()
    nse = s["noisy"] - s["clean"]
    lagmap = np.zeros((5, 5))
    for a in range(-2, 3):
        for b in range(-2, 3):
            A_ = nse[max(0, a):nse.shape[0] + min(0, a), max(0, b):nse.shape[1] + min(0, b)]
            B_ = nse[max(0, -a):nse.shape[0] + min(0, -a), max(0, -b):nse.shape[1] + min(0, -b)]
            lagmap[a + 2, b + 2] = np.mean(A_ * B_)
    lagmap /= lagmap[2, 2]
    ax = fig.add_subplot(gs[1, 0])
    kernel_panel(ax, np.round(lagmap, 2) + 0.0, "E.3: noise autocorrelation (lags -2 .. 2)", hole=-1, fmt="{:.2f}",
                 vmax=1.0)
    psnr = {}
    for col, (H, title) in enumerate(((0, "blind spot 1 x 1"), (1, "blind spot 3 x 3"))):
        S, _ = xd.de_steps(s["noisy"], 3, H)
        o, info = sc.scenario_de(s["noisy"], S=S, R=3, H=H, passes=2, engine="df", record=True)
        psnr[H] = ref.psnr(s["clean"], o)
        ax = fig.add_subplot(gs[1, 1 + col])
        kernel_panel(ax, info["weights"], f"E.3, 7 x 7, {title}: {psnr[H]:.2f} dB", hole=H, annotate=False)
    NUM["E.3_psnr_H0_H1"] = [round(psnr[0], 2), round(psnr[1], 2)]
    ax = fig.add_subplot(gs[1, 3])
    ax.axis("off")
    ax.text(0.0, 0.95, "Why the blind spot must cover the noise\ncorrelation:", fontsize=9, color=INK, va="top",
            weight="bold")
    ax.text(0.0, 0.72,
            "with a 1 x 1 blind spot the four nearest\n"
            "neighbours carry half of the centre's noise,\n"
            "the diagonal ones a quarter, and the predictor\n"
            "learns to copy it (large weights next to the\n"
            "centre): little noise is removed.\n\n"
            "A 3 x 3 blind spot leaves only taps whose\n"
            "noise is independent of the centre's; the\n"
            "weights spread over the texture period.\n\n"
            f"corrupted {ref.psnr(s['clean'], s['noisy']):.2f} dB, 1 x 1: {psnr[0]:.2f} dB,\n"
            f"3 x 3: {psnr[1]:.2f} dB",
            fontsize=8.3, color=INK2, va="top")
    for k_, ax in enumerate([a for a in fig.axes if a.get_visible() and a.axison]):
        panel_label(ax, f"({'abcdefghij'[k_]})", x=-0.04, y=1.03)
    save(fig, "algorithms", "algorithm_E.png")


# ================================================================================================== F
def figure_f():
    fig, axs = figure(2, 2, w=13.5, h=8.4)
    s = scenes.scene_f()
    x = s["clean"]
    # (a) the signal model along one row
    r = 200
    j = np.arange(0, 320)
    ax = axs[0, 0]
    ax.plot(j, (s["noisy"] - x)[r, j], color="#b9b8b0", lw=0.9, label="corruption d - x")
    ax.axhline(s["ob"][r].mean(), color=BLUE, lw=1.8, label="mean of the 16 OB pixels")
    ax.plot(j, s["ref"][r, j], color=ORANGE, lw=1.2, label="reference output (0.8 t)")
    ax.set_xlabel(f"pixel along row {r} of F.1")
    ax.set_ylabel("value")
    ax.set_title("F.1: row offset + telegraph, and the two references")
    ax.set_ylim(-0.06, 0.16)
    ax.legend(fontsize=7.5, loc="upper right", ncol=2)
    clean_axes(ax)
    # (b) the weights converging
    ax = axs[0, 1]
    s2 = xd.scene_f2()
    ar = Arith(S=1)
    xo = fe.ob_mean(ar.code(s2["dark_ob"]), 4)
    dk = ar.code(s2["dark"])
    eng = Engine(ar, 1, "lms")
    hist = []
    for _ in range(3):
        for rr in range(dk.shape[0]):
            eng.process(np.full((dk.shape[1], 1), xo[rr]), dk[rr])
            hist.append(ar.weight_real(eng.A)[0])
    wls = float(np.sum(s2["dark"] * (xo / 4096.0)[:, None]) / (np.sum((xo / 4096.0) ** 2) * s2["dark"].shape[1]))
    ax.plot(np.arange(len(hist)), hist, color=BLUE, lw=1.6, label="OB weight, dark frame x 3 (S = 1)")
    ax.axhline(wls, color=BLUE, lw=0.9, ls="--")
    _, w_on = sc.scenario_f_online(s2["noisy"], s2["ob"], S=-3)
    ar3 = Arith(S=-3)
    obc = ar3.code(s2["ob"])
    inv = ((1 << 12) + 7) // 15
    eng3 = Engine(ar3, 1, "lms")
    hon = []
    for rr in range(obc.shape[0]):
        ssum = int(obc[rr].sum())
        eng3.process((((ssum - obc[rr]) * inv) >> 12).reshape(-1, 1), obc[rr])
        hon.append(ar3.weight_real(eng3.A)[0])
    ax.plot(np.arange(len(hon)), hon, color=AQUA, lw=1.6, label="OB weight, online on the OB pixels (S = -3)")
    s3 = xd.scene_f3()
    Sc = xd.f_channel_step(s3)
    arc = Arith(S=Sc)
    engc = Engine(arc, 1, "lms")
    dd, rf = arc.code(s3["dark"]), arc.code(s3["dark_ref"])
    hc = []
    for rr in range(dd.shape[0]):
        engc.process(rf[rr].reshape(-1, 1), dd[rr])
        hc.append(arc.weight_real(engc.A)[0])
    wc = float(np.sum(s3["dark"] * s3["dark_ref"]) / np.sum(s3["dark_ref"] ** 2))
    ax.plot(np.arange(len(hc)), hc, color=ORANGE, lw=1.6, label=f"channel weight, dark frame (S = {Sc})")
    ax.axhline(wc, color=ORANGE, lw=0.9, ls="--")
    ax.set_xlabel("rows processed")
    ax.set_ylabel("weight")
    ax.set_ylim(0, 1.3)
    ax.set_title("the weights converge (dashed: least squares on the dark frame)")
    ax.legend(fontsize=7, loc="lower right")
    clean_axes(ax)
    NUM["F_weights"] = dict(ob_dark=round(float(hist[-1]), 4), ob_ls=round(wls, 4), ob_online=round(float(hon[-1]), 4),
                            channel=round(float(hc[-1]), 4), channel_ls=round(wc, 4))
    # (c) residual banding against the number of OB columns
    ax = axs[1, 0]
    rng = np.random.default_rng(12)
    Hh, Ww = 512, 512
    ns = [1, 2, 4, 8, 16, 32, 64]
    res_cal, res_one = [], []
    for N in ns:
        c = 0.03 * rng.standard_normal(Hh)
        cd = 0.03 * rng.standard_normal(Hh)
        nse = 0.01 * rng.standard_normal((Hh, Ww))
        y_ = c[:, None] + nse
        ob = c[:, None] + 0.01 * rng.standard_normal((Hh, N))
        dark = cd[:, None] + 0.01 * rng.standard_normal((Hh, Ww))
        dob = cd[:, None] + 0.01 * rng.standard_normal((Hh, N))
        o, _ = sc.scenario_f_row(y_, ob, dark, dob, S=1, log2n=int(np.log2(N)))
        res_cal.append(float(np.std((o - nse).mean(axis=1))))
        arn = Arith(S=1)
        xob = fe.ob_mean(arn.code(ob), int(np.log2(N))) / 4096.0
        res_one.append(float(np.std(c - xob)))
    ax.loglog(ns, np.array(res_one) * 4096, "s", color=AQUA, ms=6, label="w = 1: the OB mean alone")
    ax.loglog(ns, np.array(res_cal) * 4096, "o", color=BLUE, ms=6, label="w from a dark frame (S = 1)")
    nn = np.array(ns, float)
    ax.loglog(nn, 0.01 / np.sqrt(nn) * 4096, "--", color=INK2, lw=1.2, label="$\\sigma_{OB}/\\sqrt{N}$")
    ax.axhline(0.03 * 4096, color="#b9b8b0", lw=1.0)
    ax.text(1.1, 0.03 * 4096 * 1.12, "banding before correction", fontsize=7.5, color=MUTED)
    ax.set_xlabel("optical-black columns N")
    ax.set_ylabel("RMS row offset left (LSB of Q12)")
    ax.set_title("what is left is the noise of the OB mean, $\\sigma_{OB}/\\sqrt{N}$")
    ax.legend(fontsize=7.5, loc="lower left")
    clean_axes(ax)
    NUM["F_residual_lsb_vs_N"] = dict(N=ns, ob_mean_alone=[round(v * 4096, 1) for v in res_one],
                                      dark_frame_weight=[round(v * 4096, 1) for v in res_cal])
    # (d) row-offset profile before and after (F1)
    e = xd.build()["F.1"]
    img, _ = xd.run(e, s, [c for c in e.configs if c.key][0], "model")
    ax = axs[1, 1]
    rows = np.arange(0, 160)
    ax.plot(rows, (s["noisy"] - x).mean(axis=1)[rows] * 4096, color="#b9b8b0", lw=1.4, label="corrupted")
    ax.plot(rows, (img - x).mean(axis=1)[rows] * 4096, color=BLUE, lw=1.6, label="OB + channel (hardware model)")
    ax.set_xlabel("row of F.1")
    ax.set_ylabel("row mean of (image - clean) (LSB)")
    ax.set_title("banding removed row by row")
    ax.legend(fontsize=7.5)
    clean_axes(ax)
    label_all(axs)
    fig.subplots_adjust(wspace=0.26, hspace=0.38)
    save(fig, "algorithms", "algorithm_F.png")


FIGS = dict(A=figure_a, B=figure_b, C=figure_c, D=figure_d, E=figure_e, F=figure_f)

if __name__ == "__main__":
    sel = [a.upper() for a in sys.argv[1:]] or list(FIGS)
    out = RESULTS / "algorithms.json"
    if out.exists():
        NUM.update(json.loads(out.read_text()))
    for k in sel:
        t = Timer()
        FIGS[k]()
        print(k, t, flush=True)
        out.write_text(json.dumps(NUM, indent=1))
