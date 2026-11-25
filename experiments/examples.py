"""The six application examples, run through the bit-accurate models of the hardware.

    python experiments/examples.py           # compute (about 3 minutes) and plot
    python experiments/examples.py --plot

For every example: the corrupted image, the floating-point algorithm, and the fixed-point pipeline of the RTL
top with several engines. Within an algorithmic class the engines give identical images (exact LMS: serial and
folded; block LMS: row-block and DA); the delayed engines differ from exact LMS by the adaptation delay only.
The block engines take the largest power-of-two step with mu N lambda_max,row <= 1 (half of their stability
bound, docs/01-foundations.md section 1.4).
Writes results/examples.csv, figures/examples/example_*.png and the images used by the figures
(results/examples_images.npz, 20 MB, not kept under version control; --plot recomputes it when it is missing).
"""
import sys

import numpy as np

from common import write_csv, read_csv, save, Timer, RESULTS
from afarch import scenarios as sc, scenes, reference as ref, lattice, frontends as fe
from afarch.cost import worst_row_lambda, block_step
from afarch.fxp import step_exponent
from numpy.lib.stride_tricks import sliding_window_view
from scipy.ndimage import gaussian_filter1d

ROWS = []
IMGS = {}


def rec(ex, method, cls, ref_img, est, aligned=False, key=None):
    p = ref.offset_aligned_psnr(ref_img, est) if aligned else ref.psnr(ref_img, est)
    q = ref.ssim(ref_img, est - (np.mean(est - ref_img) if aligned else 0))
    ROWS.append(dict(example=ex, method=method, cls=cls, psnr=round(p, 3), ssim=round(q, 4), key=key or ""))
    if key:
        IMGS[key] = est.astype(np.float32)
    print(ROWS[-1], flush=True)
    return p


def c_tap_rows(hi, L=128, delay=8):
    """Float tap matrices of C, row by row: x_k(j) = h(refl(j - delay - k)) as in the RTL front end."""
    W = hi.shape[1]
    return (sliding_window_view(np.pad(hi[r], (L - 1 + delay, 0), mode="reflect"), L)[:W][:, ::-1]
            for r in range(hi.shape[0]))


def compute():
    t = Timer()
    # A: LED flicker (multiplicative): log ROM -> notch -> exp ROM
    s = scenes.scene_a()
    x, y = s["clean"], s["noisy"]
    eps = 0.02
    f = np.exp(ref.notch_lms(np.log(np.clip(y, 0, None) + eps), s["freqs"], mu2=1e-5, passes=3)) - eps
    rec("A", "corrupted", "-", x, y, key="A_noisy")
    rec("A", "float (log domain)", "float", x, f, key="A_float")
    for eng in ("serial", "folded", "df", "systolic"):
        rec("A", f"{eng}, log domain", sc.ENGINE_CLASS_LABEL[eng], x,
            sc.scenario_a_log(y, s["freqs"], S=17, engine=eng), key=f"A_{eng}")
    rec("A", "serial, linear domain", "exact LMS", x, sc.scenario_a(y, s["freqs"], S=17, passes=3))
    print("A", t, flush=True)
    # B: probe microscopy
    s = scenes.scene_b()
    x, y = s["clean"], s["noisy"]
    rec("B", "corrupted", "-", x, y, aligned=True, key="B_noisy")
    rec("B", "float, gated", "float", x, ref.bias_canceller(y, 0.05, "gated", tau=0.08)[0], aligned=True,
        key="B_float")
    rec("B", "float, LMS", "float", x, ref.bias_canceller(y, 0.02, "lms")[0], aligned=True)
    rec("B", "bias engine, gated", "bias", x, sc.scenario_b(y, S=4, mode="gated", tau=0.08)[0], aligned=True,
        key="B_gated")
    rec("B", "bias engine, LMS", "bias", x, sc.scenario_b(y, S=6, mode="lms")[0], aligned=True)
    rec("B", "bias engine, sign-error", "bias", x, sc.scenario_b(y, S=4, mode="sign", sk=6)[0], aligned=True)
    print("B", t, flush=True)
    # C: drifting stripes
    s = scenes.scene_c()
    x, y = s["clean"], s["noisy"]
    zc = y - y.mean(axis=1, keepdims=True)
    hi = zc - gaussian_filter1d(zc, 4.0, axis=1, mode="reflect")
    S = step_exponent(0.005, 128, hi.var())
    Sb = block_step(worst_row_lambda(c_tap_rows(hi)), y.shape[1])      # block engines: mu N lambda_row <= 1
    rec("C", "corrupted", "-", x, y, key="C_noisy")
    rec("C", "float", "float", x, ref.subband_canceller(y, alpha=0.005), key="C_float")
    for eng, SS in (("serial", S), ("folded", S), ("df", S), ("systolic", S), ("rowblock", Sb), ("da", Sb)):
        rec("C", eng + ("" if SS == S else f" (S = {SS})"), sc.ENGINE_CLASS_LABEL[eng], x,
            sc.scenario_c(y, S=SS, engine=eng), key=f"C_{eng}")
    rec("C", "A4 lattice notch (float model)", "dedicated", x, lattice.notch_image(y, k1=0.9, mu=0.032)[0],
        key="C_lattice")
    print("C", t, flush=True)
    # D: impulses on texture, gated predictor
    s = scenes.scene_d()
    x, y = s["clean"], s["noisy"]
    z = y - np.median(y)
    S = step_exponent(0.01, 24, np.var(np.clip(z, -0.5, 0.5)))
    rec("D", "corrupted", "-", x, y, key="D_noisy")
    rec("D", "float, gated", "float", x, ref.blindspot_gated(y)[0], key="D_float")
    rec("D", "median 3x3", "baseline", x, sc.median3x3(y), key="D_median")
    rec("D", "switching median, 0.15", "baseline", x, sc.median3x3(y, switch=True, thr=0.15))
    for eng in ("serial", "df", "systolic"):
        o, fl = sc.scenario_de(y, S=S, R=2, passes=3, gated=True, engine=eng)
        rec("D", f"{eng}, gated", sc.ENGINE_CLASS_LABEL[eng], x, o, key=f"D_{eng}")
        if eng == "serial":
            IMGS["D_flags"] = fl
    print("D", t, flush=True)
    # E: brick texture under heavy noise, 11 x 11 window (120 taps)
    s = scenes.scene_e()
    x, y = s["clean"], s["noisy"]
    z = y - y.mean()
    S = step_exponent(0.01, 120, z.var())
    XE = fe.window_taps(z, 5, 0).astype(float).reshape(y.shape[0], y.shape[1], -1)
    Sb = block_step(worst_row_lambda(XE[r] for r in range(y.shape[0])), y.shape[1])
    rec("E", "corrupted", "-", x, y, key="E_noisy")
    rec("E", "float, 11 x 11", "float", x, ref.blindspot_lms(y, R=5, hole=0, alpha=0.01, passes=2), key="E_float")
    for eng, SS in (("folded", S), ("df", S), ("systolic", S), ("rowblock", Sb)):
        o, info = sc.scenario_de(y, S=SS, R=5, H=0, passes=2, engine=eng, record=True)
        rec("E", eng + ("" if SS == S else f" (S = {SS})"), sc.ENGINE_CLASS_LABEL[eng], x, o, key=f"E_{eng}")
        IMGS[f"E_{eng}_weights"] = info["weights"].astype(np.float32)
    print("E", t, flush=True)
    # F: astronomy, optical black + reference channel
    s = scenes.scene_f()
    x = s["clean"]
    w = ref.train_row_weight(s["dark"], s["dark_ob"])
    y1 = s["noisy"] - w * s["ob"].mean(axis=1, keepdims=True)
    y2, _ = ref.channel_reference_canceller(y1, s["ref"], s["dark"], s["dark_ref"])
    rec("F", "corrupted", "-", x, s["noisy"], key="F_noisy")
    rec("F", "float, both references", "float", x, y2, key="F_float")
    h1, _ = sc.scenario_f_row(s["noisy"], s["ob"], s["dark"], s["dark_ob"], S=1)
    Sc = int(round(-np.log2(1e-3 / np.var(s["dark_ref"]))))
    h2, _ = sc.scenario_f_channel(h1, s["ref"], s["dark"], s["dark_ref"], S=Sc)
    rec("F", "OB, dark frame", "exact LMS", x, h1, key="F_ob")
    rec("F", "OB, online", "exact LMS", x, sc.scenario_f_online(s["noisy"], s["ob"], S=-3)[0])
    rec("F", "OB + channel", "exact LMS", x, h2, key="F_hw")
    print("F", t, flush=True)
    write_csv("examples.csv", ROWS)
    np.savez_compressed(RESULTS / "examples_images.npz", **IMGS)


def plot():
    import matplotlib.pyplot as plt
    from afarch.plotstyle import show_image, INK, INK2, MUTED, BLUE, ORANGE, AQUA, YELLOW, GRID, VIOLET
    rows = read_csv("examples.csv")
    im = np.load(RESULTS / "examples_images.npz")
    cl = {"A": scenes.scene_a, "B": scenes.scene_b, "C": scenes.scene_c, "D": scenes.scene_d, "E": scenes.scene_e,
          "F": scenes.scene_f}
    spec = {
        "A": ("LED flicker in a rolling-shutter camera", "A_serial", "serial engine, log/exp ROMs",
              (slice(0, 512), slice(0, 512)), None),
        "B": ("line offsets and drift in a probe-microscopy scan", "B_gated", "bias engine, gated",
              (slice(0, 512), slice(0, 512)), "afm"),
        "C": ("vibration stripes whose frequency drifts", "C_systolic", "systolic DLMS, 256 DSP",
              (slice(100, 356), slice(100, 356)), None),
        "D": ("10 % impulses and dead pixels on fine texture", "D_df", "direct-form DLMS, gated",
              (slice(150, 310), slice(180, 340)), None),
        "E": ("periodic texture under heavy noise", "E_df", "direct-form DLMS, 120 taps",
              (slice(160, 352), slice(160, 352)), None),
        "F": ("row banding and readout telegraph on a faint field", "F_hw", "serial engines, OB + reference",
              (slice(250, 442), slice(40, 232)), "astro"),
    }
    cls_col = {"exact LMS": BLUE, "delayed LMS": ORANGE, "block LMS": AQUA, "bias": BLUE, "float": INK2,
               "baseline": YELLOW, "dedicated": VIOLET, "-": MUTED}
    for ex, (title, key, hwlab, crop, disp) in spec.items():
        x = cl[ex]()["clean"]
        r = [q for q in rows if q["example"] == ex]
        pr = {q["method"]: float(q["psnr"]) for q in r}
        fig = plt.figure(figsize=(16.5, 3.9))
        gs = fig.add_gridspec(1, 6, width_ratios=[1, 1, 1, 1, 0.55, 1.45], wspace=0.06)
        if disp == "afm":
            f = lambda a: a - np.median(a) + 0.3  # noqa: E731
            kw = dict(vmin=0.1, vmax=0.75)
        elif disp == "astro":
            f = lambda a: np.arcsinh(np.clip(a, 0, None) / 0.03) / np.arcsinh(1 / 0.03)  # noqa: E731
            kw = {}
        else:
            f = lambda a: a  # noqa: E731
            kw = {}
        noisy = im[f"{ex}_noisy"]
        fl = im[f"{ex}_float"]
        hw = im[key]
        m_noisy = [q for q in r if q["method"] == "corrupted"][0]
        m_float = [q for q in r if q["cls"] == "float"][0]
        m_hw = [q for q in r if q["key"] == key][0]
        show_image(fig.add_subplot(gs[0]), f(noisy)[crop], f"corrupted, {float(m_noisy['psnr']):.2f} dB", **kw)
        show_image(fig.add_subplot(gs[1]), f(fl)[crop], f"floating point, {float(m_float['psnr']):.2f} dB", **kw)
        show_image(fig.add_subplot(gs[2]), f(hw)[crop], f"{hwlab}\n{float(m_hw['psnr']):.2f} dB", **kw)
        d = (hw - fl)[crop]
        ax = fig.add_subplot(gs[3])
        lim = max(4 / 4096, float(np.percentile(np.abs(d), 99.5)))
        ax.imshow(d, cmap="RdBu_r", vmin=-lim, vmax=lim, interpolation="nearest")
        ax.set_xticks([])
        ax.set_yticks([])
        for sp in ax.spines.values():
            sp.set_visible(False)
        ax.set_title(f"hardware - floating point\n(colour range +-{lim * 4096:.0f} LSB)", fontsize=8.5, color=INK, pad=3)
        ax = fig.add_subplot(gs[5])
        rr = [q for q in r if q["method"] != "corrupted"]
        names = [q["method"] for q in rr][::-1]
        vals = [float(q["psnr"]) for q in rr][::-1]
        cols = [cls_col.get(q["cls"], MUTED) for q in rr][::-1]
        y0 = np.arange(len(names))
        base = float(m_noisy["psnr"])
        ax.barh(y0, np.array(vals) - base, left=base, color=cols, height=0.62)
        for yy, v in zip(y0, vals):
            ax.text(v + 0.1, yy, f"{v:.2f}", va="center", fontsize=7, color=INK2)
        ax.set_yticks(y0)
        ax.set_yticklabels(names, fontsize=7.2)
        ax.set_xlim(base, max(vals) + 1.2)
        ax.set_xlabel("PSNR (dB)" + (", offset aligned" if ex == "B" else ""))
        ax.xaxis.grid(True, color=GRID)
        ax.set_axisbelow(True)
        for sp in ("top", "right"):
            ax.spines[sp].set_visible(False)
        ax.set_title("floating point and bit-accurate hardware", fontsize=8.5)
        fig.suptitle(f"{ex}  {title}", fontsize=11, color=INK, x=0.42, y=0.98)
        save(fig, "examples", f"example_{ex}.png")


if __name__ == "__main__":
    if "--plot" not in sys.argv or not (RESULTS / "examples.csv").exists() or \
            not (RESULTS / "examples_images.npz").exists():
        compute()
    plot()
