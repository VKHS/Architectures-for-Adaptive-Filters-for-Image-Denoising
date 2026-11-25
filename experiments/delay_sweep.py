"""What does pipelining the adaptation loop cost? PSNR against the adaptation delay D (fixed-point DLMS).

    python experiments/delay_sweep.py            # compute (about 4 minutes) and plot
    python experiments/delay_sweep.py --plot     # plot from results/delay_sweep.csv

Scenarios D (5 x 5 window, 24 taps, white noise on the test image), E (7 x 7, 48 taps, the brick texture) and C
(128 taps, drifting stripes). D = 0 is the exact LMS of lms_serial / lms_folded; the delays of lms_df
(ceil(log2 L) + 3) and lms_systolic (L + 3) are marked. Also reports mu * lambda_max of the taps against the
exact DLMS stability bound 2 sin(pi / (2 (2D + 1))), for the whole image and for the worst 64 x 64 tile: an image
is not stationary, and the loop must be stable where the local power is largest.
"""
import sys

import numpy as np

from common import write_csv, read_csv, save, Timer, RESULTS
from afarch import scenarios as sc, scenes, reference as ref, frontends as fe
from afarch.cost import dlms_mu_bound
from afarch.engines import adaptation_delay
from afarch.fxp import step_exponent
from scipy.ndimage import gaussian_filter1d


def lam_stats(X, shape, block=64):
    """lambda_max of the tap correlation over the whole image and the largest one over block x block tiles."""
    X = np.asarray(X, float)
    lg = float(np.linalg.eigvalsh(X.T @ X / len(X)).max())
    H, W = shape
    Xr = X.reshape(H, W, -1)
    loc = [np.linalg.eigvalsh(B.T @ B / len(B)).max() for B in
           (Xr[i:i + block, j:j + block].reshape(-1, X.shape[1]) for i in range(0, H, block) for j in range(0, W, block))]
    return lg, float(np.max(loc))


def lambdas():
    """(S, lambda_global, lambda_local) of the three scenarios, in real units (taps in [0, 1] pixel units)."""
    from numpy.lib.stride_tricks import sliding_window_view
    out = {}
    s = scenes.camera_gaussian()
    z = s["noisy"] - s["noisy"].mean()
    out["D"] = (step_exponent(0.01, 24, z.var()),) + lam_stats(fe.window_taps(z, 2, 0), z.shape)
    s = scenes.scene_e()
    z = s["noisy"] - s["noisy"].mean()
    out["E"] = (step_exponent(0.01, 48, z.var()),) + lam_stats(fe.window_taps(z, 3, 0), z.shape)
    s = scenes.scene_c()
    y = s["noisy"]
    zc = y - y.mean(axis=1, keepdims=True)
    hi = zc - gaussian_filter1d(zc, 4.0, axis=1, mode="reflect")
    X = np.concatenate([sliding_window_view(np.pad(hi[r], (135, 0), mode="reflect"), 128)[:512][:, ::-1]
                        for r in range(512)])
    out["C"] = (step_exponent(0.005, 128, hi.var()),) + lam_stats(X, hi.shape)
    return out


def add_lambdas(rows):
    lam = lambdas()
    for r in rows:
        S, lg, ll = lam[r["scenario"]]
        r["mu_lambda"] = round(2.0 ** -S * lg, 6)
        r["mu_lambda_local"] = round(2.0 ** -S * ll, 6)
    return rows


def compute():
    rows = []
    t = Timer()
    # ---- D
    s = scenes.camera_gaussian()
    x, y = s["clean"], s["noisy"]
    z = y - y.mean()
    S = step_exponent(0.01, 24, z.var())
    pf = ref.psnr(x, ref.blindspot_lms(y, R=2, passes=2))
    for D in (0, 1, 2, 4, 8, 16, 27, 32, 64, 128, 256):
        p = ref.psnr(x, sc.scenario_de(y, S=S, R=2, engine=f"dlms:{D}", passes=2))
        rows.append(dict(scenario="D", L=24, S=S, D=D, psnr=round(p, 3), psnr_float=round(pf, 3),
                         psnr_noisy=round(ref.psnr(x, y), 3), bound=round(dlms_mu_bound(D), 6)))
        print(rows[-1], t, flush=True)
    # ---- E
    s = scenes.scene_e()
    x, y = s["clean"], s["noisy"]
    z = y - y.mean()
    S = step_exponent(0.01, 48, z.var())
    pf = ref.psnr(x, ref.blindspot_lms(y, R=3, hole=0, passes=2))
    for D in (0, 2, 4, 9, 16, 32, 51, 64, 128, 256):
        p = ref.psnr(x, sc.scenario_de(y, S=S, R=3, H=0, engine=f"dlms:{D}", passes=2))
        rows.append(dict(scenario="E", L=48, S=S, D=D, psnr=round(p, 3), psnr_float=round(pf, 3),
                         psnr_noisy=round(ref.psnr(x, y), 3), bound=round(dlms_mu_bound(D), 6)))
        print(rows[-1], t, flush=True)
    # ---- C
    s = scenes.scene_c()
    x, y = s["clean"], s["noisy"]
    zc = y - y.mean(axis=1, keepdims=True)
    hi = zc - gaussian_filter1d(zc, 4.0, axis=1, mode="reflect")
    S = step_exponent(0.005, 128, hi.var())
    pf = ref.psnr(x, ref.subband_canceller(y, alpha=0.005))
    for D in (0, 2, 4, 10, 16, 32, 64, 131, 256, 512):
        p = ref.psnr(x, sc.scenario_c(y, S=S, engine=f"dlms:{D}"))
        rows.append(dict(scenario="C", L=128, S=S, D=D, psnr=round(p, 3), psnr_float=round(pf, 3),
                         psnr_noisy=round(ref.psnr(x, y), 3), bound=round(dlms_mu_bound(D), 6)))
        print(rows[-1], t, flush=True)
    write_csv("delay_sweep.csv", add_lambdas(rows))


def plot():
    import matplotlib.pyplot as plt
    from afarch.plotstyle import clean_axes, BLUE, ORANGE, AQUA, INK2, MUTED, RED
    rows = read_csv("delay_sweep.csv")
    fig, axs = plt.subplots(1, 2, figsize=(11.5, 4.1), gridspec_kw=dict(wspace=0.28))
    ax = axs[0]
    colors = dict(D=BLUE, E=ORANGE, C=AQUA)
    names = dict(D="D, 24 taps (camera, white noise)", E="E, 48 taps (brick texture)", C="C, 128 taps (stripes)")
    lo, hi = -0.45, 0.35
    for sc_, col in colors.items():
        r = [q for q in rows if q["scenario"] == sc_]
        D = np.array([int(q["D"]) for q in r])
        p = np.array([float(q["psnr"]) for q in r])
        base = p[D == 0][0]
        dp = p - base
        ok = dp > lo
        ax.plot(np.maximum(D[ok], 0.5), dp[ok], "-o", color=col, ms=4, label=names[sc_])
        if (~ok).any():
            txt = "D = " + " and ".join(str(d_) for d_ in D[~ok]) + " diverge\n(" + \
                  ", ".join(f"{v:.1f}" for v in p[~ok]) + " dB)"
            for k, d_ in enumerate(D[~ok]):
                ax.annotate(txt if k == 0 else "", xy=(d_, lo), xytext=(90, lo + 0.17), ha="right", va="center",
                            fontsize=7.5, color=col, arrowprops=dict(arrowstyle="-|>", color=col, lw=0.9))
        L = int(r[0]["L"])
        for eng, mk in (("df", "s"), ("systolic", "^")):
            d = adaptation_delay(eng, L)
            if d in D:
                ax.plot([d], [dp[D == d][0]], mk, color=col, ms=9, mfc="white", mew=1.8)
    ax.set_ylim(lo, hi)
    ax.plot([], [], "s", color=INK2, mfc="white", mew=1.5, ms=8, label="lms_df: D = ceil(log2 L) + 3")
    ax.plot([], [], "^", color=INK2, mfc="white", mew=1.5, ms=8, label="lms_systolic: D = L + 3")
    ax.set_xscale("log")
    ax.set_xticks([0.5, 1, 2, 4, 8, 16, 32, 64, 128, 256, 512])
    ax.set_xticklabels(["0", "1", "2", "4", "8", "16", "32", "64", "128", "256", "512"])
    ax.set_xlabel("adaptation delay D (samples)")
    ax.set_ylabel("PSNR change against exact LMS (dB)")
    ax.set_title("fixed-point PSNR against the adaptation delay")
    ax.axhline(0, color=MUTED, lw=0.8)
    ax.legend(loc="upper left", fontsize=7.5)
    clean_axes(ax)
    ax = axs[1]
    Ds = np.arange(0, 600)
    ax.plot(np.maximum(Ds, 0.5), [2 * np.sin(np.pi / (2 * (2 * d + 1))) for d in Ds], color=RED, lw=1.6,
            label=r"stability bound $2\sin\frac{\pi}{2(2D+1)}$")
    for sc_, col in colors.items():
        r = [q for q in rows if q["scenario"] == sc_]
        ml = float(r[0]["mu_lambda"])
        mll = float(r[0]["mu_lambda_local"])
        ax.axhline(ml, color=col, lw=1.0, ls=":")
        ax.axhline(mll, color=col, lw=1.4, ls="--",
                   label=fr"{sc_}: $\mu\lambda_{{max}}$ worst tile {mll:.2g} (whole image {ml:.2g})")
        L = int(r[0]["L"])
        for eng, mk in (("df", "s"), ("systolic", "^")):
            d = adaptation_delay(eng, L)
            ax.plot([d], [mll], mk, color=col, ms=8, mfc="white", mew=1.6)
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xticks([0.5, 1, 4, 16, 64, 256])
    ax.set_xticklabels(["0", "1", "4", "16", "64", "256"])
    ax.set_xlabel("adaptation delay D (samples)")
    ax.set_ylabel(r"$\mu\,\lambda_{max}$")
    ax.set_ylim(2e-4, 3)
    ax.set_title("step-size margin of the pipelined engines")
    ax.text(0.97, 0.96, "dashed: worst 64 x 64 tile\ndotted: whole image", transform=ax.transAxes, ha="right",
            va="top", fontsize=7.5, color=INK2)
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.16), ncol=2, fontsize=7.2)
    clean_axes(ax)
    save(fig, "results", "delay_sweep.png")


if __name__ == "__main__":
    if "--relambda" in sys.argv:
        write_csv("delay_sweep.csv", add_lambdas(read_csv("delay_sweep.csv")))
    elif "--plot" not in sys.argv or not (RESULTS / "delay_sweep.csv").exists():
        compute()
    plot()
