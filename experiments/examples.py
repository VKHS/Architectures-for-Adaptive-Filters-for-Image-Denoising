"""The eighteen application examples, three per scenario, run through the bit-accurate models of the hardware.

    python experiments/examples.py              # compute every example (about 15 minutes) and plot
    python experiments/examples.py A.2 C        # recompute some examples (or a scenario), keep the others
    python experiments/examples.py --plot       # plot from results/examples.csv and the image archive

For every example (experiments/example_defs.py): the corrupted image, the floating-point algorithm, baselines
where they apply, and the fixed-point pipeline of the scenario top with several engines. Within an algorithmic
class the engines give identical images (exact LMS: serial and folded; block LMS: row-block and DA); the delayed
engines differ from exact LMS by the adaptation delay only. The block engines take the largest power-of-two step
with mu N lambda_max,row <= 1 (half of their stability bound, docs/01-foundations.md section 1.4).
experiments/examples_hw.py runs the same configurations through the RTL and HLS tops.

Writes results/examples.csv, figures/examples/example_<X>_<k>.png (one per example), figures/examples/
examples_<scenario>.png (the three examples of a scenario), figures/examples/overview.png, and the images of the
figures (results/examples_images.npz, about 60 MB, not under version control; --plot recomputes it if missing).
"""
import sys

import numpy as np

from common import write_csv, read_csv, save, Timer, RESULTS
from example_defs import build, run, score, select

IMAGES = RESULTS / "examples_images.npz"


def compute(sel):
    exs = build()
    sel = select(list(exs), sel)
    rows = [r for r in (read_csv("examples.csv") if (RESULTS / "examples.csv").exists() and sel else [])
            if r["example"] not in sel]
    imgs = dict(np.load(IMAGES)) if IMAGES.exists() and sel else {}
    for eid in sel or list(exs):
        t = Timer()
        e = exs[eid]
        s = e.scene()
        x = s["clean"]

        def rec(method, cls, img, key=None):
            p, q = score(e, x, img)
            rows.append(dict(example=eid, method=method, cls=cls, psnr=round(p, 3), ssim=round(q, 4), key=key or ""))
            if key:
                imgs[key] = img.astype(np.float32)
            print(rows[-1], flush=True)

        rec("corrupted", "-", s["noisy"], f"{eid}_noisy")
        for k, (label, fn) in enumerate(e.floats):
            rec(label, "float", fn(s), f"{eid}_float" if k == 0 else None)
        for label, cls, fn in e.baselines:
            rec(label, cls, fn(s))
        for c in e.configs:
            img, raw = run(e, s, c, "model")
            rec(c.label, c.cls, img, f"{eid}_hw" if c.key else None)
            if c.key and c.kind == "de" and c.kw["gated"]:
                imgs[f"{eid}_flags"] = raw[:, 1].reshape(x.shape).astype(bool)
            if c.key and c.kind == "b":
                imgs[f"{eid}_track"] = (raw[:, 1].reshape(x.shape) / 4096.0).astype(np.float32)
        print(eid, t, flush=True)
    order = {k: i for i, k in enumerate(exs)}
    rows.sort(key=lambda r: order[r["example"]])
    write_csv("examples.csv", rows)
    np.savez_compressed(IMAGES, **imgs)


# --------------------------------------------------------------------------------------------- figures
def display(e):
    if e.disp == "afm":
        return lambda a: a - np.median(a) + 0.3, dict(vmin=0.1, vmax=0.75)
    if e.disp == "page":
        return lambda a: a - np.median(a) + 0.88, dict(vmin=0.0, vmax=1.0)
    if e.disp == "astro":
        return lambda a: np.arcsinh(np.clip(a - np.median(a) + 0.02, 0, None) / 0.03) / np.arcsinh(1 / 0.03), {}
    return lambda a: a, {}


def plot():
    import textwrap
    import matplotlib.pyplot as plt
    from afarch.plotstyle import show_image, INK, INK2, MUTED, BLUE, ORANGE, AQUA, YELLOW, GRID, VIOLET
    exs = build()
    rows = read_csv("examples.csv")
    im = np.load(IMAGES)
    cls_col = {"exact LMS": BLUE, "delayed LMS": ORANGE, "block LMS": AQUA, "bias": BLUE, "float": INK2,
               "baseline": YELLOW, "dedicated": VIOLET, "-": MUTED}
    hw_label = {}
    for eid, e in exs.items():
        r = [q for q in rows if q["example"] == eid]
        if not r:
            continue
        key = [c for c in e.configs if c.key][0]
        hw_label[eid] = key.label
        f, kw = display(e)
        crop = e.crop
        m_noisy = [q for q in r if q["method"] == "corrupted"][0]
        m_float = [q for q in r if q["cls"] == "float"][0]
        m_hw = [q for q in r if q["key"] == f"{eid}_hw"][0]
        noisy, fl, hw = im[f"{eid}_noisy"], im[f"{eid}_float"], im[f"{eid}_hw"]
        fig = plt.figure(figsize=(16.5, 3.9))
        gs = fig.add_gridspec(1, 6, width_ratios=[1, 1, 1, 1, 0.8, 1.45], wspace=0.06)
        al = ", offset aligned" if e.aligned else ""
        show_image(fig.add_subplot(gs[0]), f(noisy)[crop], f"corrupted, {float(m_noisy['psnr']):.2f} dB", **kw)
        show_image(fig.add_subplot(gs[1]), f(fl)[crop], f"{m_float['method']}\n{float(m_float['psnr']):.2f} dB", **kw)
        show_image(fig.add_subplot(gs[2]), f(hw)[crop], f"{key.label} (hardware)\n{float(m_hw['psnr']):.2f} dB",
                   **kw)
        d = (hw - fl)[crop]
        if e.aligned:
            d = d - np.mean(hw - fl)
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
        corr = float(m_noisy["psnr"])
        base = min(corr, min(vals)) - (1.0 if min(vals) < corr else 0.0)
        ax.barh(y0, np.array(vals) - base, left=base, color=cols, height=0.62)
        for yy, v in zip(y0, vals):
            ax.text(v + 0.1, yy, f"{v:.2f}", va="center", fontsize=7, color=INK2)
        if base < corr:
            ax.axvline(corr, color=MUTED, lw=0.9, ls="--")
            ax.text(corr, -0.5, " corrupted", fontsize=6.8, color=MUTED, va="center")
        ax.set_yticks(y0)
        ax.set_yticklabels(names, fontsize=7.2)
        ax.set_xlim(base, max(vals) + 0.12 * (max(vals) - base) + 0.6)
        ax.set_xlabel("PSNR (dB)" + al)
        ax.xaxis.grid(True, color=GRID)
        ax.set_axisbelow(True)
        for sp in ("top", "right"):
            ax.spines[sp].set_visible(False)
        ax.set_title("floating point and bit-accurate hardware", fontsize=8.5)
        fig.suptitle(f"{eid}  {e.title}", fontsize=11, color=INK, x=0.42, y=0.98)
        save(fig, "examples", f"example_{eid.replace('.', '_')}.png")

    # the three examples of every scenario: corrupted above, hardware below
    for scen in "ABCDEF":
        ids = [k for k in exs if k[0] == scen and f"{k}_hw" in im.files]
        if not ids:
            continue
        fig, axs = plt.subplots(2, len(ids), figsize=(4.1 * len(ids), 8.4), squeeze=False)
        for k, eid in enumerate(ids):
            e = exs[eid]
            f, kw = display(e)
            r = {q["key"]: q for q in rows if q["example"] == eid}
            show_image(axs[0, k], f(im[f"{eid}_noisy"])[e.crop],
                       textwrap.fill(f"{eid}  {e.title}", 44) +
                       f"\ncorrupted, {float(r[f'{eid}_noisy']['psnr']):.2f} dB", **kw)
            show_image(axs[1, k], f(im[f"{eid}_hw"])[e.crop],
                       f"{hw_label[eid]} (hardware), {float(r[f'{eid}_hw']['psnr']):.2f} dB", **kw)
        fig.subplots_adjust(wspace=0.04, hspace=0.2)
        save(fig, "examples", f"examples_{scen}.png")

    # overview: the first example of every scenario
    names = {"A": "A  adaptive notch", "B": "B  bias canceller", "C": "C  canceller, no reference",
             "D": "D  blind-spot predictor", "E": "E  line enhancer", "F": "F  reference sensor"}
    pick = {k: f"{k}.1" for k in "ABCDEF"}
    if any(f"{k}_hw" not in im.files for k in pick.values()):
        return
    fig, axs = plt.subplots(2, 6, figsize=(19.5, 7.6))
    for k, scen in enumerate("ABCDEF"):
        eid = pick[scen]
        e = exs[eid]
        f, kw = display(e)
        r = {q["key"]: q for q in rows if q["example"] == eid}
        c0, c1 = e.crop
        sq = min((c0.stop or 512) - (c0.start or 0), (c1.stop or 512) - (c1.start or 0), 256)
        crop = (slice(c0.start or 0, (c0.start or 0) + sq), slice(c1.start or 0, (c1.start or 0) + sq))
        title = textwrap.fill(f"{eid} {e.title}", 34)
        if title.count("\n") == 0:
            title += "\n"
        axs[0, k].text(0.5, 1.18, names[scen], transform=axs[0, k].transAxes, ha="center", va="bottom", fontsize=10,
                       fontweight="bold", color=INK)
        show_image(axs[0, k], f(im[f"{eid}_noisy"])[crop],
                   f"{title}\ncorrupted, {float(r[f'{eid}_noisy']['psnr']):.1f} dB", **kw)
        show_image(axs[1, k], f(im[f"{eid}_hw"])[crop],
                   f"{hw_label[eid]} (hardware)\n{float(r[f'{eid}_hw']['psnr']):.1f} dB", **kw)
    fig.subplots_adjust(wspace=0.05, hspace=0.14)
    save(fig, "examples", "overview.png")


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if "--plot" not in sys.argv or not (RESULTS / "examples.csv").exists() or not IMAGES.exists():
        compute(args)
    plot()
