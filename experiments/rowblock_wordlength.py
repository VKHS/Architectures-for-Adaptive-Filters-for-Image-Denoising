"""Two fixed-point questions that decide an architecture.

    python experiments/rowblock_wordlength.py          # compute (about 6 minutes) and plot
    python experiments/rowblock_wordlength.py --plot

1. Row-block LMS (lms_rowblock, lms_da) sums N = 512 gradients before it updates, so its step must satisfy
   mu N lambda_max < 2. PSNR of exact LMS and row-block LMS against the step exponent S (mu = 2^-S), D and C.
2. Weight word length. A classic weight REGISTER with FW fractional bits loses every update smaller than half an
   LSB (stalling); the accumulator of this repository keeps every update exactly and only rounds the weight it
   uses. PSNR against FW for both, scenario D.
"""
import sys

import numpy as np

from common import write_csv, read_csv, save, Timer, RESULTS
from afarch import scenarios as sc, scenes, reference as ref, frontends as fe
from afarch.fxp import Arith, step_exponent
from afarch.cost import worst_row_lambda
from scipy.ndimage import gaussian_filter1d


def lambda_c(hi):
    """lambda_max of the delayed-reference taps of C (float taps; np.pad reflect as in the software)."""
    from numpy.lib.stride_tricks import sliding_window_view
    X = np.concatenate([sliding_window_view(np.pad(hi[r], (135, 0), mode="reflect"), 128)[:512][:, ::-1]
                        for r in range(0, 512, 4)])
    return float(np.linalg.eigvalsh(X.T @ X / len(X)).max())


def relambda():
    """Add the whole-image and the worst-row lambda_max (mu N lambda_row < 2 is the block-LMS condition)."""
    from numpy.lib.stride_tricks import sliding_window_view
    rows = read_csv("rowblock_step.csv")
    s = scenes.camera_gaussian()
    z = s["noisy"] - s["noisy"].mean()
    XD = fe.window_taps(z, 2, 0).astype(float).reshape(512, 512, -1)
    lamD = float(np.linalg.eigvalsh(XD.reshape(-1, 24).T @ XD.reshape(-1, 24) / (512 * 512)).max())
    lamD_row = worst_row_lambda(XD[r] for r in range(512))
    s = scenes.scene_c()
    y = s["noisy"]
    zc = y - y.mean(axis=1, keepdims=True)
    hi = zc - gaussian_filter1d(zc, 4.0, axis=1, mode="reflect")
    lamC = lambda_c(hi)
    lamC_row = worst_row_lambda(sliding_window_view(np.pad(hi[r], (135, 0), mode="reflect"), 128)[:512][:, ::-1]
                                for r in range(512))
    for r in rows:
        S = int(r["S"])
        lg, lrow = (lamD, lamD_row) if r["scenario"] == "D" else (lamC, lamC_row)
        r["mu_lambda"] = round(2.0 ** -S * lg, 6)
        r["mu_N_lambda"] = round(2.0 ** -S * lg * 512, 4)
        r["mu_N_lambda_row"] = round(2.0 ** -S * lrow * 512, 4)
    write_csv("rowblock_step.csv", rows)


def compute_wordlength_a():
    """A (log domain, mu = 2^-17): the small step makes a short weight register stall completely."""
    t = Timer()
    rows = []
    s = scenes.scene_a()
    x, y = s["clean"], s["noisy"]
    for FW in (16, 18, 20, 22, 24, 26):
        for kind in ("register", "accumulator"):
            ar = Arith(S=17, FW=FW, WW=FW + 4, qupdate=(kind == "register"))
            p = ref.psnr(x, sc.scenario_a_log(y, s["freqs"], S=17, ar=ar))
            rows.append(dict(scenario="A", storage=kind, FW=FW, WW=FW + 4, S=17, psnr=round(p, 3)))
            print(rows[-1], t, flush=True)
    write_csv("wordlength_a.csv", rows)


def compute():
    t = Timer()
    rows = []
    s = scenes.camera_gaussian()
    x, y = s["clean"], s["noisy"]
    z = y - y.mean()
    X = fe.window_taps(z, 2, 0)
    lamD = float(np.linalg.eigvalsh(X[::13].T @ X[::13] / len(X[::13])).max())
    for S in range(5, 15):
        for eng in ("serial", "rowblock"):
            p = ref.psnr(x, sc.scenario_de(y, S=S, R=2, engine=eng, passes=2))
            rows.append(dict(scenario="D", engine=eng, S=S, psnr=round(p, 3), psnr_noisy=round(ref.psnr(x, y), 3),
                             mu_lambda=round(2.0 ** -S * lamD, 6), mu_N_lambda=round(2.0 ** -S * lamD * 512, 4)))
            print(rows[-1], t, flush=True)
    s = scenes.scene_c()
    x, y = s["clean"], s["noisy"]
    zc = y - y.mean(axis=1, keepdims=True)
    hi = zc - gaussian_filter1d(zc, 4.0, axis=1, mode="reflect")
    lamC = lambda_c(hi)
    for S in range(4, 14):
        for eng in ("serial", "rowblock"):
            p = ref.psnr(x, sc.scenario_c(y, S=S, engine=eng))
            rows.append(dict(scenario="C", engine=eng, S=S, psnr=round(p, 3), psnr_noisy=round(ref.psnr(x, y), 3),
                             mu_lambda=round(2.0 ** -S * lamC, 6), mu_N_lambda=round(2.0 ** -S * lamC * 512, 4)))
            print(rows[-1], t, flush=True)
    write_csv("rowblock_step.csv", rows)
    relambda()                                   # whole-image and worst-row lambda_max of both scenes

    rows = []
    s = scenes.camera_gaussian()
    x, y = s["clean"], s["noisy"]
    S = step_exponent(0.01, 24, (y - y.mean()).var())
    for FW in (10, 12, 14, 16, 18, 20, 22):
        for kind in ("register", "accumulator"):
            ar = Arith(S=S, FW=FW, WW=FW + 4, qupdate=(kind == "register"))
            p = ref.psnr(x, sc.scenario_de(y, S=S, R=2, engine="serial", passes=2, ar=ar))
            rows.append(dict(storage=kind, FW=FW, WW=FW + 4, S=S, psnr=round(p, 3)))
            print(rows[-1], t, flush=True)
    for FD in (8, 10, 12, 14):
        ar = Arith(S=S, FD=FD, FW=FD + 8, WW=FD + 12)
        p = ref.psnr(x, sc.scenario_de(y, S=S, R=2, engine="serial", passes=2, ar=ar))
        rows.append(dict(storage="accumulator, data FD = %d" % FD, FW=FD + 8, WW=FD + 12, S=S, psnr=round(p, 3)))
        print(rows[-1], t, flush=True)
    rows.append(dict(storage="float reference", FW="", WW="", S="", psnr=round(ref.psnr(x, ref.blindspot_lms(y)), 3)))
    write_csv("wordlength.csv", rows)


def plot():
    import matplotlib.pyplot as plt
    from afarch.plotstyle import clean_axes, BLUE, ORANGE, MUTED, RED
    rb = read_csv("rowblock_step.csv")
    wl = read_csv("wordlength.csv")
    fig, axs = plt.subplots(1, 3, figsize=(15, 3.9), gridspec_kw=dict(wspace=0.3))
    for ax, scn, title in ((axs[0], "D", "D benchmark, cameraman (24 taps)"),
                           (axs[1], "C", "C, drifting stripes (128 taps)")):
        for eng, col, lab in (("serial", BLUE, "exact LMS (serial, folded)"),
                              ("rowblock", ORANGE, "row-block LMS (rowblock, DA)")):
            r = [q for q in rb if q["scenario"] == scn and q["engine"] == eng]
            S = np.array([int(q["S"]) for q in r])
            p = np.array([float(q["psnr"]) for q in r])
            ax.plot(S, p, "-o", color=col, ms=4, label=lab)
        r = [q for q in rb if q["scenario"] == scn and q["engine"] == "rowblock"]
        S = np.array([int(q["S"]) for q in r])
        mnl = np.array([float(q["mu_N_lambda_row"]) for q in r])
        ok = mnl < 2
        if (~ok).any():
            ax.axvspan(S.min() - 0.5, S[~ok].max() + 0.5, color=RED, alpha=0.07, lw=0)
            ax.text(S[~ok].max() + 0.8, 15, "shaded: row-block predicted\nunstable, " +
                    r"$\mu N \lambda_{max,row} > 2$", color=RED, fontsize=7.5, ha="left", va="center")
        noisy = float(r[0]["psnr_noisy"])
        ax.axhline(noisy, color=MUTED, lw=0.8, ls=":")
        ax.text(S.max(), noisy + 0.5, "noisy input", color=MUTED, fontsize=7, ha="right", va="bottom")
        ax.set_xlabel(r"step exponent S  ($\mu = 2^{-S}$)")
        ax.set_ylabel("PSNR (dB)")
        ax.set_title(title)
        clean_axes(ax)
    for ax in axs[:2]:
        ax.set_ylim(3, None)
    h, lab = axs[0].get_legend_handles_labels()
    fig.legend(h, lab, loc="upper center", ncol=2, fontsize=8, frameon=False, bbox_to_anchor=(0.36, 0.01))
    ax = axs[2]
    wa = read_csv("wordlength_a.csv")
    best = {"D": max(float(q["psnr"]) for q in wl if q["storage"] == "accumulator"),
            "A": max(float(q["psnr"]) for q in wa if q["storage"] == "accumulator")}
    for scn, rows_, mk in (("A", wa, "o"), ("D", wl, "s")):
        for kind, col, ls in (("register", RED, "-"), ("accumulator", BLUE, "--")):
            r = [q for q in rows_ if q["storage"] == kind]
            ax.plot([int(q["FW"]) for q in r], [float(q["psnr"]) - best[scn] for q in r], ls, marker=mk, color=col,
                    ms=4.5, lw=1.6, label=f"{scn} " + rf"($\mu=2^{{-{r[0]['S']}}}$), " +
                    ("weight register" if kind == "register" else "accumulator"))
    ax.set_xlabel("weight fraction bits FW (weight word = FW + 4 bits)")
    ax.set_ylabel("PSNR change (dB)")
    ax.set_ylim(-5, 0.6)
    ax.set_title("stalling: a register loses updates below LSB / 2")
    ax.legend(loc="center right", fontsize=7.2)
    clean_axes(ax)
    save(fig, "results", "rowblock_wordlength.png")


if __name__ == "__main__":
    if "--relambda" in sys.argv:
        relambda()
    elif "--a" in sys.argv:
        compute_wordlength_a()
    elif "--plot" not in sys.argv or not (RESULTS / "wordlength.csv").exists():
        compute()
        compute_wordlength_a()
    plot()
