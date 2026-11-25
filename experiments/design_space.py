"""Design space: cycles per sample against multipliers for the scenarios' tap counts, with Yosys LUT counts.

    python experiments/design_space.py       # writes results/design_space.csv, figures/results/design_space.png

II comes from the formulas of afarch.cost (checked against the RTL by sim/test_engines.py); the clock a video
format needs is II x pixel rate. Multipliers map one-to-one onto DSP48E1 slices; LUT and FF counts are Yosys
synth_xilinx results where the configuration was synthesized (results/synth_engines.csv), blank otherwise.
"""
from common import write_csv, read_csv, save
from afarch.cost import model, RATES

SCEN = [("D", 24), ("E", 48), ("C", 128)]


def compute():
    syn = {(r["engine"], int(r["L"]), r["P"] or "", int(r["TDL"])): r for r in read_csv("synth_engines.csv")}
    rows = []
    for scn, L in SCEN:
        cfgs = [("serial", 1)] + [("folded", P) for P in (1, 2, 4, 6, 8, 12, 16, 24, 32, 48, 64, 128) if P <= L] + \
               [("df", 1), ("systolic", 1), ("rowblock", 1), ("da", 1)]
        for eng, P in cfgs:
            m = model(eng, L, P)
            tdl = 1 if (L == 128 and eng in ("df", "systolic", "rowblock")) else 0
            s = syn.get((eng, L, str(P) if eng == "folded" else "", tdl), {})
            row = dict(scenario=scn, L=L, engine=eng, P=P if eng == "folded" else "", mult=m["mult"], II=m["II"],
                       D=m["D"] if m["D"] is not None else "block", LUT=s.get("LUT", ""), FF=s.get("FF", ""),
                       DSP_yosys=s.get("DSP48E1", ""))
            for name, rate in RATES.items():
                row["MHz " + name] = round(m["II"] * rate / 1e6, 1)
            rows.append(row)
    write_csv("design_space.csv", rows)
    return rows


def plot(rows):
    import matplotlib.pyplot as plt
    from afarch.plotstyle import clean_axes, BLUE, ORANGE, AQUA, INK2, RED
    fig, axs = plt.subplots(1, 3, figsize=(15, 4.6), gridspec_kw=dict(wspace=0.28))
    rate1 = RATES["512x512 @ 30 fps"]
    rate2 = RATES["1920x1080 @ 60 fps"]
    for ax, (scn, L) in zip(axs, SCEN):
        r = [q for q in rows if q["scenario"] == scn]
        fo = [q for q in r if q["engine"] == "folded"]
        ax.plot([max(q["mult"], 0.5) for q in fo], [q["II"] for q in fo], "-o", color=BLUE, ms=4,
                label="lms_folded, P = 1 .. L")
        for q in fo:
            if q["P"] in (1, 4, L, {24: 6, 48: 12, 128: 16}[L]):
                ax.annotate(f"P={q['P']}", (q["mult"], q["II"]), textcoords="offset points", xytext=(4, 4),
                            fontsize=6.8, color=BLUE)
        style = dict(serial=("s", BLUE, "lms_serial"), df=("D", ORANGE, "lms_df"), systolic=("^", ORANGE, "lms_systolic"),
                     rowblock=("v", AQUA, "lms_rowblock"), da=("P", AQUA, "lms_da (no multiplier)"))
        for eng, (mk, col, lab) in style.items():
            q = [x for x in r if x["engine"] == eng][0]
            xm = max(q["mult"], 0.5)
            off = {"df": 0.88, "systolic": 1.0, "rowblock": 1.13}.get(eng, 1.0)
            ax.plot([xm * off], [q["II"]], mk, color=col, ms=9, mfc="white" if eng in ("systolic", "da") else col,
                    mew=1.8, label=lab, ls="none")
            if eng in ("serial", "da"):
                lut = f", {q['LUT']} LUT" if q["LUT"] != "" else ""
                ax.annotate(f"{q['mult']} mult{lut}", (xm, q["II"]), textcoords="offset points",
                            xytext=(7, -11 if eng == "da" else 5), fontsize=6.6, color=INK2)
        pipe = {x["engine"]: x for x in r if x["engine"] in ("df", "systolic", "rowblock")}
        ax.text(2 * L * 0.85, 1.55, f"{2 * L} mult, II = 1\nLUT: df {pipe['df']['LUT']}, systolic "
                f"{pipe['systolic']['LUT']},\nrow-block {pipe['rowblock']['LUT']}", fontsize=6.6, color=INK2,
                ha="right", va="bottom")
        for f_clk, ls in ((200e6, "--"),):
            ax.axhline(f_clk / rate1, color=RED, lw=1.0, ls=ls)
            ax.text(2 * 2 * L + 40, f_clk / rate1 * 1.12, "512 x 512 @ 30 fps, 200 MHz", fontsize=7, color=RED,
                    ha="right")
            ax.axhline(f_clk / rate2, color=RED, lw=1.0, ls=":")
            ax.text(0.42, f_clk / rate2 * 1.12, "1080p60, 200 MHz", fontsize=7, color=RED, ha="left")
        ax.set_xscale("log")
        ax.set_yscale("log")
        ax.set_xlim(0.35, 2 * 2 * L + 50)
        ax.set_ylim(0.7, 600)
        ax.set_xlabel("multipliers (= DSP48E1; DA plotted at 0.5)")
        ax.set_ylabel("II, clock cycles per pixel")
        ax.set_title(f"{scn}: L = {L} taps")
        clean_axes(ax, grid_x=True)
        if scn == "D":
            ax.legend(loc="upper right", fontsize=7)
    fig.text(0.5, -0.04, "A design meets a format at a clock f when II <= f / pixel rate: below the red line. The 200 MHz "
             "lines are a reference clock for the comparison, not a timing result.", ha="center", fontsize=8,
             color=INK2)
    save(fig, "results", "design_space.png")


if __name__ == "__main__":
    plot(compute())
