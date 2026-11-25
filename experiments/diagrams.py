"""Block diagrams of the architectures (figures/diagrams/*.png).

    python experiments/diagrams.py            # all
    python experiments/diagrams.py serial df  # some
"""
import sys

from common import FIG
from afarch.plotstyle import (HwDiagram, REG_FILL as REG_FILL_ALT, INK, INK2, MUTED, BLUE, ORANGE, AQUA, RED,
                              NEUTRAL, BLUE_LIGHT, ORANGE_LIGHT, AQUA_LIGHT, MEM_FILL, DSP_FILL)

OUT = FIG / "diagrams"
OUT.mkdir(parents=True, exist_ok=True)
LOOP = RED


def save(d, name):
    d.save(OUT / name)
    print("wrote", f"figures/diagrams/{name}", flush=True)


# --------------------------------------------------------------------------------------------- the loop
def lms_loop():
    d = HwDiagram(14.0, 5.6)
    d.title("The LMS recursion as hardware: one loop, one register (a), and the same loop pipelined (b)")

    def tap(x0, delayed):
        ytop, ybot = 3.55, 1.35
        # inputs
        d.text(x0 + 0.1, ytop + 0.55, r"$x_k(n)$", fs=9)
        d.wire([(x0 + 0.1, ytop + 0.4), (x0 + 0.1, ytop), (x0 + 0.95, ytop)])
        m1 = d.op(x0 + 1.15, ytop, "x")
        # weight register and view
        A = d.reg(x0 + 1.15, 2.45, w=0.62, h=0.5, label=r"$A_k$", fs=8.5)
        d.wire([A["t"], m1["b"]], color=LOOP, lw=1.6)
        d.text(x0 + 1.55, 2.95, r"$w_k=A_k\gg V$", fs=7.5, color=INK2, ha="left")
        # product register (b)
        xp = x0 + 1.15
        if delayed:
            r1 = d.reg(x0 + 1.75, ytop, label="")
            d.wire([m1["r"], r1["l"]], color=LOOP, lw=1.6)
            xp = x0 + 1.75
            src = r1["r"]
        else:
            src = m1["r"]
        # adder tree
        tree_x = x0 + (2.65 if delayed else 2.35)
        tw = 0.95 if delayed else 0.75
        d.block(tree_x, ytop, tw, 0.75, "adder\ntree" + ("\nT regs" if delayed else ""), fs=7.5,
                fill=NEUTRAL, edge=LOOP if True else INK2)
        d.wire([src, (tree_x - tw / 2, ytop)], color=LOOP, lw=1.6)
        d.text(tree_x, ytop + 0.62, "other taps", fs=7, color=MUTED)
        d.wire([(tree_x, ytop + 0.5), (tree_x, ytop + 0.38)], color=MUTED, lw=1.0)
        # subtract
        sx = tree_x + tw / 2 + 0.55
        s = d.op(sx, ytop, "-")
        d.wire([(tree_x + tw / 2, ytop), s["l"]], color=LOOP, lw=1.6)
        d.text(sx, ytop + 0.62, r"$d(n)$", fs=9)
        d.wire([(sx, ytop + 0.48), s["t"]])
        d.text(sx - 0.33, ytop + 0.12, r"$y$", fs=8, color=INK2)
        # error register (b)
        ex = sx + 0.55
        if delayed:
            r2 = d.reg(ex, ytop)
            d.wire([s["r"], r2["l"]], color=LOOP, lw=1.6)
            eout = r2["r"]
            ex2 = ex + 0.4
        else:
            eout = s["r"]
            ex2 = sx + 0.4
        d.text(ex2 + 0.02, ytop + 0.18, r"$e$", fs=9, ha="left")
        d.wire([eout, (ex2 + 0.25, ytop), (ex2 + 0.25, ybot), (ex2 - 0.05, ybot)], color=LOOP, lw=1.6)
        d.text(ex2 + 0.35, (ytop + ybot) / 2, r"$\mu=2^{-S}$:" + "\na bit slice,\nno hardware", fs=7, color=INK2,
               ha="left")
        # update multiplier and its x
        m2 = d.op(ex2 - 0.25, ybot, "x")
        d.wire([(ex2 - 0.05, ybot), m2["r"]], color=LOOP, lw=1.6, head=False)
        if delayed:
            dl = d.block(x0 + 2.65, 0.55, 1.3, 0.38, r"$z^{-(T+2)}$ on $x_k$", fs=7.5, fill=MEM_FILL)
            d.wire([(x0 + 0.1, ytop + 0.4), (x0 + 0.1, 0.55), dl["l"]], ls="--", color=INK2, lw=1.0)
            d.wire([dl["r"], (ex2 - 0.25, 0.55), m2["b"]], color=INK2, lw=1.0)
            r3 = d.reg(ex2 - 0.85, ybot)
            d.wire([m2["l"], r3["r"]], color=LOOP, lw=1.6)
            gsrc = r3["l"]
        else:
            d.wire([(x0 + 0.1, ytop + 0.4), (x0 + 0.1, 0.75), (ex2 - 0.25, 0.75), m2["b"]], ls="--", color=INK2,
                   lw=1.0)
            gsrc = m2["l"]
        # accumulate
        ad = d.op(x0 + 1.15, ybot, "+")
        d.wire([gsrc, ad["r"]], color=LOOP, lw=1.6)
        d.wire([ad["t"], A["b"]], color=LOOP, lw=1.6)
        d.curved((x0 + 1.47, 2.3), (x0 + 1.32, ybot + 0.1), rad=-0.6, color=INK2, lw=0.9)
        d.text(x0 + 1.67, 1.95, r"$A_k$", fs=7.5, color=INK2, ha="left")
        d.text(x0 + 0.62, ybot - 0.02, r"$g_k=e\,x_k$", fs=8, color=INK2, ha="right")

    d.region(0.15, 0.25, 6.45, 4.75, "(a) exact LMS: lms_serial, lms_folded", color=BLUE, fs=9)
    tap(0.45, False)
    d.note(0.45, 0.55, "loop: multiply + adder tree + subtract + multiply + add,\nwith ONE register: "
           r"$T_\infty = 2T_\times + (\lceil\log_2 L\rceil + 2)T_+$", fs=7.8, color=LOOP)
    d.region(6.85, 0.25, 7.0, 4.75, "(b) delayed LMS: lms_df", color=ORANGE, fs=9)
    tap(7.1, True)
    d.note(12.15, 2.1, "T + 4 registers in\nthe loop: the update\nof sample n is used\nfrom n + T + 4 on,\n"
           r"$D = T + 3$, and $T_\infty$" + "\nshrinks by D + 1", fs=7.4, color=LOOP)
    save(d, "lms_loop.png")


# ------------------------------------------------------------------------------------------- engines
def _err_unit(d, x, y, w=1.5, h=1.05):
    return d.block(x, y, w, h, "error unit\n" + r"$e=\mathrm{sat}(d-y)$" + "\ngate, output select", fs=7.5,
                   fill=NEUTRAL)


def serial():
    d = HwDiagram(13.6, 6.0)
    d.title("lms_serial: exact LMS on one multiplier (one DSP48E1)")
    d.subtitle("Filter pass (L cycles), error, update pass (L cycles): II = 2L + 3 cycles per sample, "
               "L + 3 when the sample does not adapt.")
    # inputs
    d.text(0.55, 2.35, r"in_x" + "\n(L taps)", fs=8)
    xr = d.block(1.9, 2.0, 1.25, 0.8, "tap registers\nxr[0..L-1]", fs=7.5, fill=MEM_FILL)
    d.bus([(0.55, 2.0), xr["l"]], "L x 16", at=0.45)
    mx = d.mux(3.0, 2.0, h=0.85)
    d.text(3.0, 1.45, "L:1, k", fs=7, color=INK2)
    d.bus([xr["r"], (2.87, 2.0)], None)
    A = d.mem(1.9, 4.0, 1.7, 0.95, "accumulators A[k]\nLUTRAM, L x 48", fs=7.5)
    v = d.block(3.45, 4.0, 0.95, 0.55, "view\n" + r"$\gg V$, sat", fs=7.2)
    d.bus([A["r"], v["l"]], "48", at=0.45)
    m2 = d.mux(4.55, 3.55, h=1.15, label="FILT | UPD")
    d.bus([v["r"], (4.42, 4.0)], "24")
    # DSP
    d.region(5.0, 2.35, 2.2, 1.75, "DSP48E1", color=BLUE)
    mul = d.op(5.55, 3.25, "x")
    d.bus([m2["r"], (5.0, 3.55), (5.0, 3.25), mul["l"]], None)
    d.bus([mx["r"], (3.5, 2.0), (3.5, 2.6), (5.55, 2.6), mul["b"]], "16", at=0.5)
    pq = d.reg(6.25, 3.25, label="M")
    d.wire([mul["r"], pq["l"]])
    ad = d.op(6.75, 3.25, "+")
    d.wire([pq["r"], ad["l"]])
    acc = d.reg(7.55, 3.25, w=0.55, label="acc", fs=7)
    d.wire([ad["r"], acc["l"]])
    d.wire([(7.83, 3.25), (7.95, 3.25), (7.95, 3.85), (6.75, 3.85), ad["t"]], color=INK2, lw=1.0)
    d.text(7.0, 4.3, r"acc starts at RND $=2^{FW-1}$" + "\n(rounding for free)", fs=7, color=INK2)
    yb = d.block(8.75, 3.25, 1.0, 0.55, r"$y=$sat" + "\n" + r"(acc$\gg FW$)", fs=7.2)
    d.wire([(7.95, 3.25), yb["l"]])
    eu = _err_unit(d, 10.55, 3.25)
    d.wire([yb["r"], eu["l"]])
    d.text(10.55, 4.35, "d, p, adapt", fs=8)
    d.wire([(10.55, 4.2), eu["t"]])
    d.wire([eu["r"], (12.0, 3.25)])
    d.text(12.55, 3.25, "o, y, e,\nflag", fs=8)
    er = d.reg(10.55, 1.75, w=0.5, label="e", fs=8)
    d.wire([eu["b"], er["t"]])
    d.wire([er["l"], (4.3, 1.75), (4.3, 3.2), (4.42, 3.2)], color=INK2)
    # write-back
    wb = d.op(1.9, 5.05, "+")
    d.wire([(6.25, 3.04), (6.25, 1.25), (0.6, 1.25), (0.6, 5.05), wb["l"]], color=ORANGE, lw=1.3)
    d.text(3.9, 1.05, r"update pass: $g_k = e\,x_k$ from the same multiplier", fs=7.5, color=ORANGE)
    d.wire([A["t"], wb["b"]], color=ORANGE, lw=1.3, head=False)
    d.curved((2.15, 5.05), (2.6, 4.47), rad=-0.5, color=ORANGE, lw=1.3)
    d.text(3.0, 5.15, r"$A_k \leftarrow A_k + g_k$" + "  (write-back, one cycle later)", fs=7.5, color=ORANGE,
           ha="left")
    # schedule
    y0 = 0.25
    segs = [("accept", 1, NEUTRAL), ("filter: L cycles", 6, BLUE_LIGHT), ("drain", 1, NEUTRAL),
            ("error", 1, NEUTRAL), ("update: L cycles", 6, ORANGE_LIGHT)]
    x = 5.2
    for lab, wdt, col in segs:
        d.rect(x, y0, wdt * 0.42, 0.42, col, ec=INK2, lw=0.6, z=3)
        d.text(x + wdt * 0.21, y0 + 0.21, lab, fs=7)
        x += wdt * 0.42
    d.text(5.1, y0 + 0.21, "per sample:", fs=7.5, ha="right", color=INK2)
    d.text(x + 0.15, y0 + 0.21, "= 2L + 3 cycles", fs=7.5, ha="left", color=INK2)
    save(d, "engine_serial.png")


def folded():
    d = HwDiagram(13.6, 7.1)
    d.title("lms_folded: exact LMS on P lanes, one fused pass per sample (2P DSP48E1)")
    d.subtitle("Tap k = mP + p lives in lane p. Each cycle every lane updates one weight with the previous "
               "sample's error and immediately\nfilters with it, so the weights of y(n) hold every update up to n - 1: "
               "II = ceil(L/P) + ceil(log2 P) + 5 cycles.")
    lanes = [(4.65, "lane 0"), (2.8, "lane 1"), (0.6, "lane P-1")]
    for yl, name in lanes:
        d.region(0.3, yl - 0.05, 7.6, 1.6, name, color=BLUE)
        yc = yl + 0.72
        xp = d.block(1.15, yc + 0.32, 1.05, 0.42, r"$x(n-1)$ bank", fs=7, fill=MEM_FILL)
        xc = d.block(1.15, yc - 0.32, 1.05, 0.42, r"$x(n)$ bank", fs=7, fill=MEM_FILL)
        m1 = d.op(2.35, yc + 0.32, "x")
        d.wire([xp["r"], m1["l"]])
        d.text(2.75, yc + 0.68, r"$e(n-1)$", fs=7.2, color=INK2, ha="left")
        d.wire([(2.7, yc + 0.68), (2.35, yc + 0.68), m1["t"]], color=INK2, lw=1.0)
        q = d.reg(2.95, yc + 0.32, label="")
        d.wire([m1["r"], q["l"]])
        ab = d.mem(4.15, yc + 0.36, 1.15, 0.58, "A bank\n" + r"$\lceil L/P\rceil$ x 48", fs=6.8)
        ad = d.op(4.15, yc - 0.36, "+")
        d.wire([q["r"], (3.35, yc + 0.32), (3.35, yc - 0.36), ad["l"]], color=ORANGE)
        d.wire([ab["b"], ad["t"]], color=ORANGE, lw=1.0)
        d.curved((4.33, yc - 0.22), (4.73, yc + 0.12), rad=0.5, color=ORANGE, lw=1.0)
        vw = d.block(5.3, yc - 0.36, 0.75, 0.42, "view", fs=7)
        d.wire([ad["r"], vw["l"]])
        m2 = d.op(6.25, yc - 0.36, "x")
        d.wire([vw["r"], m2["l"]])
        d.wire([xc["r"], (1.9, yc - 0.32), (1.9, yc - 0.68), (6.25, yc - 0.68), m2["b"]], color=INK2, lw=1.0)
        la = d.reg(7.2, yc - 0.36, w=0.5, label=r"$\Sigma_p$", fs=7)
        d.wire([m2["r"], la["l"]])
    d.text(4.1, 2.55, r"$\vdots$", fs=14, color=MUTED)
    tree = d.block(9.0, 3.25, 1.0, 2.8, "adder tree\n" + r"$\lceil\log_2 P\rceil$" + "\nregister\nlevels", fs=7.5,
                   fill=NEUTRAL)
    for (yl, _), yt in zip(lanes, (4.3, 3.25, 2.2)):
        yo = yl + 0.36
        d.wire([(7.45, yo), (8.1, yo), (8.1, yt), (8.5, yt)])
    eu = _err_unit(d, 10.95, 3.25)
    d.wire([tree["r"], eu["l"]])
    d.wire([eu["r"], (12.4, 3.25)])
    d.text(12.9, 3.25, "o, y, e", fs=8)
    d.text(10.95, 4.35, "d, p", fs=8)
    d.wire([(10.95, 4.2), eu["t"]])
    d.wire([(10.95, 2.72), (10.95, 0.25), (1.0, 0.25)], color=INK2, lw=1.0, ls="--")
    d.text(6.0, 0.4, "e(n) goes to the update multiplier of every lane for the next pass", fs=7.2, color=INK2)
    d.text(9.0, 5.05, "RND preloaded\nin lane 0", fs=7, color=INK2)
    save(d, "engine_folded.png")


def df():
    d = HwDiagram(13.6, 6.9)
    d.title("lms_df: fully parallel direct-form DLMS, one sample per clock (2L DSP48E1)")
    d.subtitle("Every tap has a filter multiplier and an update multiplier; the adder tree is pipelined. The loop holds "
               "T + 4 registers,\nso the update of sample n is used from n + T + 4 on: D = T + 3, T = ceil(log2 L).")
    taps = [(4.55, "tap 0"), (2.85, "tap 1"), (0.55, "tap L-1")]
    for yt, name in taps:
        d.region(1.25, yt - 0.08, 5.6, 1.5, name, color=ORANGE)
        yc = yt + 0.66
        A = d.reg(2.0, yc, w=0.55, h=0.55, label=r"$A_k$", fs=8)
        vw = d.block(2.95, yc + 0.34, 0.62, 0.36, "view", fs=6.8)
        d.wire([(2.28, yc + 0.12), (2.45, yc + 0.34), vw["l"]])
        m1 = d.op(3.85, yc + 0.34, "x")
        d.wire([vw["r"], m1["l"]])
        d.text(3.65, yc + 0.72, r"$x_k(n)$", fs=7.2, color=INK2, ha="right")
        d.wire([(3.68, yc + 0.72), (3.85, yc + 0.72), m1["t"]], color=INK2, lw=1.0)
        p1 = d.reg(4.5, yc + 0.34, label="")
        d.wire([m1["r"], p1["l"]])
        d.wire([p1["r"], (7.35, yc + 0.34)])
        m2 = d.op(5.7, yc - 0.33, "x")
        q = d.reg(4.85, yc - 0.33, label="")
        d.wire([m2["l"], q["r"]], color=ORANGE)
        ad = d.op(3.0, yc - 0.33, "+")
        d.wire([q["l"], ad["r"]], color=ORANGE)
        d.wire([ad["l"], (2.0, yc - 0.33), A["b"]], color=ORANGE)
        d.wire([(6.45, yc - 0.33), m2["r"]], color=ORANGE, lw=1.2)
        d.text(6.5, yc - 0.12, "e", fs=7.5, color=ORANGE, ha="left")
        d.text(5.95, yc - 0.72, r"$x_k(n-T-2)$", fs=7, color=INK2, ha="left")
        d.wire([(5.9, yc - 0.72), (5.7, yc - 0.72), m2["b"]], color=INK2, lw=1.0)
    d.text(6.4, 2.35, r"$\vdots$", fs=14, color=MUTED)
    d.bus([(0.55, 5.5), (0.55, 0.6)], "L x 16", head=False, at=0.15)
    d.text(0.55, 5.72, "x(n)", fs=8)
    d.note(1.45, 2.55, "x(n) feeds the filter multipliers directly and the update multipliers\nthrough a "
           r"$z^{-(T+2)}$" + " delay line (SRL)", fs=7.0)
    tree = d.block(7.9, 3.3, 1.1, 3.8, "pipelined\nadder tree\n\nT register\nlevels", fs=7.5, fill=NEUTRAL)
    eu = _err_unit(d, 9.95, 3.3)
    d.wire([tree["r"], eu["l"]])
    d.text(9.95, 4.42, "d, p delayed\nT + 1 steps", fs=7.2, color=INK2)
    d.wire([(9.95, 4.15), eu["t"]], color=INK2, lw=1.0)
    er = d.reg(9.95, 1.65, w=0.5, label="e", fs=8)
    d.wire([eu["b"], er["t"]])
    d.wire([er["l"], (9.2, 1.65), (9.2, 0.25), (6.45, 0.25), (6.45, 5.55), (6.45, 5.55)], color=ORANGE, lw=1.3,
           head=False)
    d.text(8.0, 0.4, "e(n), registered, to every update multiplier", fs=7.2, color=ORANGE)
    d.wire([eu["r"], (11.45, 3.3)])
    d.text(11.95, 3.3, "o, y, e", fs=8)
    d.note(10.95, 6.0, "every register advances on\nadv = valid | shift | drain,\nso D counts samples; drain\n"
           "steps finish pending updates\n(row end, frame end)", fs=7.2)
    save(d, "engine_df.png")


def systolic():
    d = HwDiagram(13.6, 5.9)
    d.title("lms_systolic: systolic DLMS, one sample per clock, local wiring only (2L DSP48E1)")
    d.subtitle("The partial sum moves one cell per clock (the DSP48 PCOUT -> PCIN cascade); the error walks down an "
               "error chain the same way.\nIn the skewed weights w^_j(m) = w_j(m + j) this is a DLMS with one delay "
               "for every tap: D = L + 3.")
    xs = [1.45, 4.3, 8.45]
    names = ["cell 0", "cell 1", "cell L-1"]
    for k, (x0, name) in enumerate(zip(xs, names)):
        d.region(x0 - 0.85, 0.3, 2.45, 4.05, name, color=ORANGE)
        sk = d.block(x0 + 0.45, 3.8, 1.05, 0.36, "skew line", fs=7, fill=MEM_FILL)
        d.wire([(x0 + 0.45, 4.6), sk["t"]], color=INK2, lw=1.0)
        A = d.reg(x0 - 0.35, 2.85, w=0.5, h=0.5, label=r"$A_j$", fs=8)
        m1 = d.op(x0 + 0.45, 2.85, "x")
        d.wire([sk["b"], m1["t"]], color=INK2, lw=1.0)
        d.wire([A["r"], m1["l"]])
        P = d.reg(x0 + 0.45, 2.15, label="P")
        d.wire([m1["b"], P["t"]])
        ad = d.op(x0 + 0.45, 1.3, "+")
        d.wire([P["b"], ad["t"]])
        S_ = d.reg(x0 + 1.15, 1.3, label="S")
        d.wire([ad["r"], S_["l"]], color=BLUE, lw=1.4)
        q = d.reg(x0 - 0.35, 2.2, label="")
        d.wire([q["t"], A["b"]], color=ORANGE)
        m2 = d.op(x0 - 0.35, 1.68, "x")
        d.wire([m2["t"], q["b"]], color=ORANGE)
        ec = d.reg(x0 - 0.35, 0.68, w=0.42, h=0.38, label="e", fs=7)
        d.wire([ec["t"], m2["b"]], color=ORANGE)
        d.text(x0 - 0.62, 1.68, r"$x_j$", fs=7, color=INK2, ha="right")
        d.wire([(x0 - 0.6, 1.68), m2["l"]], color=INK2, lw=1.0)
    # partial-sum chain
    d.text(0.12, 1.48, "RND", fs=7, color=BLUE, ha="left")
    d.wire([(0.12, 1.3), (xs[0] + 0.28, 1.3)], color=BLUE, lw=1.4)
    d.wire([(xs[0] + 1.32, 1.3), (xs[1] + 0.28, 1.3)], color=BLUE, lw=1.4)
    d.wire([(xs[1] + 1.32, 1.3), (6.9, 1.3)], color=BLUE, lw=1.4, head=False)
    d.text(7.15, 1.3, r"$\cdots$", fs=14, color=MUTED)
    d.wire([(7.4, 1.3), (xs[2] + 0.28, 1.3)], color=BLUE, lw=1.4)
    eu = _err_unit(d, 11.9, 1.3, w=1.6, h=1.0)
    d.wire([(xs[2] + 1.32, 1.3), eu["l"]], color=BLUE, lw=1.4)
    d.text(10.25, 1.5, "y(m)", fs=7.5, color=BLUE)
    d.text(11.9, 2.15, "d, p delayed L + 1", fs=7.2, color=INK2)
    d.wire([(11.9, 2.0), eu["t"]], color=INK2, lw=1.0)
    d.wire([eu["r"], (13.05, 1.3)])
    d.text(13.3, 1.55, "o, y,\ne", fs=7.5)
    # error chain
    d.wire([(11.9, 0.8), (11.9, 0.12), (0.3, 0.12), (0.3, 0.68), (xs[0] - 0.56, 0.68)], color=ORANGE, lw=1.3)
    d.wire([(xs[0] - 0.14, 0.68), (xs[1] - 0.56, 0.68)], color=ORANGE, lw=1.3)
    d.wire([(xs[1] - 0.14, 0.68), (6.9, 0.68)], color=ORANGE, lw=1.3, head=False)
    d.wire([(7.4, 0.68), (xs[2] - 0.56, 0.68)], color=ORANGE, lw=1.3)
    d.text(7.15, 0.68, r"$\cdots$", fs=14, color=MUTED)
    d.text(7.15, 0.32, "error chain:\none register per cell", fs=7, color=ORANGE)
    d.text(7.15, 1.72, "partial sum:\nPCOUT -> PCIN", fs=7, color=BLUE)
    d.text(1.0, 4.82, r"$x_j(m)$: skewed by j steps for the filter and L + 2 more for the update.  TDL mode: one "
           "shared chain of 3L + 1 words, x_j(m - j) = x_0(m - 2j) (two registers per tap)", fs=7.5, color=INK2,
           ha="left")
    save(d, "engine_systolic.png")


def rowblock():
    d = HwDiagram(13.6, 5.4)
    d.title("lms_rowblock: block LMS with the block = one image row (2L DSP48E1, no loop inside a row)")
    d.subtitle("The weights are frozen along a row, so the filter is a plain pipelined FIR. Each tap accumulates "
               "its gradient G_k; the last\nsample of the row commits A_k <- A_k + G_k during horizontal blanking "
               "(a drain of T + 4 steps). Stable for mu N lambda_max < 2.")
    d.region(0.3, 1.0, 5.1, 2.6, "filter with frozen weights", color=AQUA)
    A = d.reg(1.0, 2.9, w=0.6, h=0.55, label=r"$A_k$", fs=8)
    m1 = d.op(2.2, 2.9, "x")
    d.wire([A["r"], m1["l"]])
    d.text(2.2, 3.4, r"$x_k(n)$", fs=8)
    d.wire([(2.2, 3.28), m1["t"]], color=INK2, lw=1.0)
    tree = d.block(3.6, 2.4, 1.0, 1.6, "pipelined\nadder\ntree", fs=7.5, fill=NEUTRAL)
    d.wire([m1["r"], (3.1, 2.9)])
    eu = _err_unit(d, 6.4, 2.4, w=1.5)
    d.wire([tree["r"], eu["l"]])
    d.wire([eu["t"], (6.4, 3.45)])
    d.text(6.4, 3.6, "o, y, e", fs=8)
    d.region(7.6, 1.0, 3.6, 2.6, "gradient correlator", color=AQUA)
    m2 = d.op(8.3, 2.4, "x")
    d.wire([eu["r"], m2["l"]], color=AQUA)
    d.text(8.3, 3.05, r"$x_k(n)$ delayed", fs=7.5, color=INK2)
    d.wire([(8.3, 2.9), m2["t"]], color=INK2, lw=1.0)
    ad = d.op(9.3, 2.4, "+")
    d.wire([m2["r"], ad["l"]], color=AQUA)
    G = d.reg(10.2, 2.4, w=0.6, h=0.55, label=r"$G_k$", fs=8)
    d.wire([ad["r"], G["l"]], color=AQUA)
    d.wire([(10.5, 2.4), (10.75, 2.4), (10.75, 1.55), (9.3, 1.55), ad["b"]], color=INK2, lw=1.0)
    cm = d.op(10.2, 0.45, "+")
    d.wire([G["b"], cm["t"]], color=AQUA)
    d.wire([cm["l"], (1.0, 0.45), A["b"]], color=AQUA, lw=1.5)
    d.text(5.5, 0.62, r"commit at the row end: $A_k \leftarrow A_k + G_k$, $G_k \leftarrow 0$  (in blanking)",
           fs=7.5, color=AQUA)
    d.note(11.45, 3.45, "per tap: 2 multipliers,\n2 accumulators (A, G).\nThe DA engine computes\nthe "
           "same numbers\nwithout multipliers.", fs=7.3)
    save(d, "engine_rowblock.png")


def da():
    d = HwDiagram(13.6, 5.8)
    d.title("lms_da: distributed arithmetic, no multiplier (block LMS, bit-exact with lms_rowblock)")
    d.subtitle("Taps in groups of four; each group keeps the 16 partial sums of its weights. One bit of every tap "
               "per cycle addresses the tables;\nan adder tree and a shift-accumulator (Horner, MSB first) give the "
               "exact inner product in WD cycles: II = WD + ceil(log2 ceil(L/4)) + 3.")
    for k, (yg, name) in enumerate([(3.7, "group 0: taps 0..3"), (2.25, "group 1: taps 4..7"),
                                    (0.6, "group G-1")]):
        d.region(0.3, yg - 0.15, 5.0, 1.2, name, color=AQUA)
        yc = yg + 0.4
        for i in range(4):
            d.block(0.75 + i * 0.42, yc, 0.36, 0.42, "", fill=MEM_FILL)
            d.text(0.75 + i * 0.42, yc, f"x{i}", fs=6.5)
        d.text(1.38, yc - 0.38, "bit b of each tap", fs=6.5, color=INK2)
        tb = d.mem(3.3, yc, 1.25, 0.7, "table\n16 x 26", fs=7)
        d.wire([(2.15, yc), tb["l"]])
        d.text(2.4, yc + 0.17, "4-bit\naddress", fs=6, color=INK2)
        d.wire([tb["r"], (5.6, yc)])
    d.text(2.8, 1.85, r"$\vdots$", fs=14, color=MUTED)
    tree = d.block(6.25, 2.4, 1.0, 3.0, "adder\ntree", fs=7.5, fill=NEUTRAL)
    hs = d.op(7.75, 2.4, "+")
    d.wire([tree["r"], hs["l"]])
    hr = d.reg(8.65, 2.4, w=0.6, label="hacc", fs=7)
    d.wire([hs["r"], hr["l"]])
    d.wire([(8.95, 2.4), (9.15, 2.4), (9.15, 3.0), (7.75, 3.0), hs["t"]], color=INK2, lw=1.0)
    d.text(8.45, 3.25, r"$\times 2$ (wiring); $-$ for the sign bit", fs=7, color=INK2)
    eu = _err_unit(d, 10.6, 2.4, w=1.45)
    d.wire([(9.15, 2.4), eu["l"]])
    d.wire([eu["r"], (12.0, 2.4)])
    d.text(12.45, 2.4, "o, y, e", fs=8)
    d.region(7.35, 0.25, 6.0, 1.25, "bit-serial gradient (overlaps the next sample)", color=AQUA, label_pos="bl")
    d.note(7.5, 1.32, r"$t_k \leftarrow 2t_k \pm e[b]\,x_k$  (one adder per tap)" + "\n" +
           r"$G_k \leftarrow G_k + t_k$;  row end: $A_k \leftarrow A_k + G_k$, rebuild the tables (16 cycles)",
           fs=7.5, color=INK)
    d.wire([(10.6, 1.87), (10.6, 1.5)], color=AQUA)
    save(d, "engine_da.png")


def accumulator():
    d = HwDiagram(13.6, 5.6)
    d.title("The weight accumulator: every update kept exactly; the step size is a choice of bits")
    wb, x0, y0 = 0.2, 0.7, 2.75
    V = 11                                         # S = 7: V = 2 FD - FW + S = 24 - 20 + 7

    def bx(b):                                     # left edge of bit b (bit 47 on the left)
        return x0 + (47 - b) * wb

    for b in range(48):
        col = BLUE_LIGHT if V <= b < V + 24 else ("#fdecea" if b >= V + 24 else "#eeeee8")
        d.rect(bx(b), y0, wb, 0.4, col, ec=INK2, lw=0.4, z=3)
    for b, lab in ((47, "47"), (V + 23, str(V + 23)), (V, str(V)), (0, "0")):
        d.text(bx(b) + wb / 2, y0 - 0.15, lab, fs=6.5, color=INK2)
    d.text(bx(47) - 0.12, y0 + 0.2, r"$A_k$", fs=10, ha="right")

    def bracket(b_hi, b_lo, y, text, col, up=True):
        xa, xb = bx(b_hi) + 0.03, bx(b_lo) + wb - 0.03
        dy = 0.12 if up else -0.12
        d.ax.plot([xa, xa, xb, xb], [y, y + dy, y + dy, y], color=col, lw=1.0, zorder=4)
        d.text((xa + xb) / 2, y + dy + (0.2 if up else -0.22), text, fs=7.5, color=col)

    bracket(47, V + 24, y0 + 0.47, "sign and guard bits", RED)
    bracket(V + 23, V, y0 + 0.47, r"weight view $w_k$ = $A_k \gg V$, saturated to 24 bits (FW = 20)", BLUE)
    bracket(V - 1, 0, y0 + 0.47, "below the view", INK2)
    # update product
    yg = y0 - 1.0
    for b in range(32):
        d.rect(bx(b), yg, wb, 0.4, ORANGE_LIGHT, ec=INK2, lw=0.4, z=3)
    d.text(bx(31) - 0.15, yg + 0.2, "+", fs=12, ha="right")
    d.text((bx(31) + bx(0) + wb) / 2, yg - 0.25, r"update product $g = e\,x_k$: 16 x 16 = 32 bits, 2FD = 24 "
           "fractional bits, added at bit 0: no shift, no rounding", fs=7.5, color=ORANGE)
    # view to the filter multiplier
    xm = (bx(V + 23) + bx(V) + wb) / 2
    fm = d.block(xm, 4.65, 3.6, 0.45, "24-bit weight to the filter multiplier (DSP48E1 port A, 25 bits)", fs=7.5,
                 fill=DSP_FILL, edge=BLUE)
    d.wire([(xm, y0 + 0.95), fm["b"]], color=BLUE)
    # explanation
    d.note(10.75, 4.85, r"$V = 2FD - FW + S$" + "\n\n" +
           r"$\mu = 2^{-S}$ is WHICH bits form" + "\nthe weight: no multiplier.\n\n"
           "An update far below the\nweight LSB is not lost: it\nwaits in the low bits until\nthe carries reach the "
           "view.\nA weight REGISTER rounds\neach update and stalls\nwhen |mu e x| < LSB / 2.", fs=7.8)
    d.region(0.6, 0.15, 9.95, 1.0, "", color=INK2, ls=":")
    d.note(0.75, 1.07, "DSP48E1 mapping: the update DSP runs in MACC mode, P <- P + A x B with A = e, B = x_k, so its "
           "48-bit P register IS A_k.\nThe filter DSP takes the view on A and the tap on B; its P cascade (PCOUT -> "
           "PCIN) carries the partial sum,\npreloaded with RND = 2^(FW-1) through the C port: the rounding of y costs "
           "nothing.", fs=7.6)
    save(d, "weight_accumulator.png")


# --------------------------------------------------------------------------------------- front ends
def window():
    d = HwDiagram(13.6, 6.3)
    d.title("window_gen: raster stream -> (2R+1) x (2R+1) windows with reflected borders (D, E, median)")
    d.subtitle("Rows go round-robin into 2R + 2 row buffers. An address generator reads every buffer at the column "
               "refl(t), t = -R .. W-1+R, and picks the\nbuffers of rows refl(i + a): the padding of the software "
               "(np.pad reflect) costs no storage and no multiplexers on the window.")
    d.text(0.55, 3.2, "pixel\nstream", fs=8)
    wr = d.block(1.85, 3.2, 1.2, 0.6, "row r ->\nbuffer r mod NB", fs=7)
    d.wire([(0.95, 3.2), wr["l"]])
    names = ["row i-2", "row i-1", "row i", "row i+1", "row i+2", "row i+3 (filling)"]
    for k, nm in enumerate(names):
        yb = 4.6 - k * 0.55
        bb = d.mem(3.85, yb, 1.75, 0.42, nm, fs=6.8, rows=3)
        d.wire([(2.45, 3.2), (2.75, 3.2), (2.75, yb), (2.97, yb)], color=INK2, lw=0.8)
        if k < 5:
            d.wire([bb["r"], (5.35, yb)], color=INK2, lw=1.0)
    ag = d.block(3.85, 5.25, 2.1, 0.42, "column address refl(t)", fs=7.2, fill=NEUTRAL)
    d.text(3.85, 1.0, "NB = 2R + 2 block RAMs\n(W x 32 bits: tap and d planes)", fs=7, color=INK2)
    mx = d.block(5.75, 3.7, 0.7, 2.5, "row\nselect\nrefl(i+a)", fs=7, fill="white")
    K = 5
    gx, gy, cs = 7.0, 2.55, 0.42
    for i in range(K):
        for j in range(K):
            blind = (i == 2 and j == 2)
            d.rect(gx + j * cs, gy + (K - 1 - i) * cs, cs, cs, "#fdecea" if blind else REG_FILL_ALT, ec=INK2, lw=0.6,
                   z=3)
    d.text(gx + 2.5 * cs, gy + 2.5 * cs, "x", fs=8, color=RED)
    for i in range(K):
        d.wire([(6.1, gy + (K - 1 - i) * cs + cs / 2), (gx + 5 * cs + 0.25, gy + (K - 1 - i) * cs + cs / 2)],
               color=INK2, lw=0.7, head=False) if False else None
    d.wire([(6.1, 3.6), (gx - 0.08, 3.6)], color=INK)
    d.text(gx + 2.5 * cs, gy + 5 * cs + 0.22, "register window, shifts one column per read", fs=7.2, color=INK2)
    d.text(gx + 2.5 * cs, gy - 0.25, "centre (2H+1)^2 = blind spot", fs=7, color=RED)
    tp = d.block(10.35, 3.6, 1.55, 0.75, "tap select\n" + r"$L=(2R{+}1)^2-(2H{+}1)^2$", fs=7.2, fill=NEUTRAL)
    d.bus([(gx + 5 * cs + 0.05, 3.6), tp["l"]], None)
    d.wire([tp["r"], (12.25, 3.6)])
    d.text(12.8, 3.6, "engine", fs=8)
    d.text(10.35, 2.75, "d = centre of plane 1", fs=7, color=INK2)
    # inset: the read order
    ax = d.fig.add_axes([0.655, 0.075, 0.21, 0.2])
    import numpy as np
    W, R = 16, 2
    t = np.arange(-R, W + R)
    a = np.where(t < 0, -t, np.where(t > W - 1, 2 * (W - 1) - t, t))
    ax.step(np.arange(len(t)), a, where="mid", color=BLUE, lw=1.4)
    ax.set_xlabel("read cycle in the row (W = 16, R = 2)", fontsize=6.5)
    ax.set_xticks([0, 2, 6, 10, 14, 17, 19])
    ax.set_yticks([0, 2, 5, 10, 15])
    ax.set_ylabel("column", fontsize=6.5)
    ax.tick_params(labelsize=6)
    for sp in ("top", "right"):
        ax.spines[sp].set_visible(False)
    ax.set_title("V at the start, Lambda at the end", fontsize=7)
    d.note(0.4, 0.95, "per output row: W + 2R read cycles\noutput row i starts when input row\nmin(i + R, H - 1) is "
           "complete; the input\nmay run at most R + 1 rows ahead\n(in_ready): no buffer is overwritten\nwhile it is "
           "still needed", fs=7.0)
    save(d, "window_gen.png")


def scen_a():
    d = HwDiagram(13.6, 5.75)
    d.title("Scenario A: adaptive notch with plane-wave references generated in raster order")
    d.subtitle("Phase of harmonic k at pixel (i, j): i U_k + j V_k (mod 2^32), from two accumulators: no multiplier. "
               "Each harmonic's cosine ROM gives cos on one port\nand sin, 2^(NA-2) entries back, on the other. "
               "Multiplicative interference (LED flicker) goes through a log ROM before and an exp ROM after (model).")
    d.text(0.55, 2.4, "pixel\nstream", fs=8)
    lg = d.block(1.85, 2.4, 1.15, 0.5, "log ROM\n(model)", fs=7, fill=MEM_FILL)
    d.wire([(1.0, 2.4), lg["l"]])
    sub = d.op(3.1, 2.4, "-")
    d.wire([lg["r"], sub["l"]])
    d.text(3.1, 2.95, "offset", fs=7, color=INK2)
    d.wire([(3.1, 2.82), sub["t"]], color=INK2, lw=1.0)
    rp = d.reg(1.6, 3.85, w=0.9, h=0.5, label="row phase", fs=7)
    pp = d.reg(3.3, 3.85, w=0.9, h=0.5, label="pixel phase", fs=7)
    d.text(1.6, 4.35, "+U per row", fs=7, color=INK2)
    d.text(3.3, 4.35, "+V per pixel", fs=7, color=INK2)
    d.wire([rp["r"], pp["l"]], color=INK2, lw=1.0)
    rnd = d.block(4.85, 3.85, 1.1, 0.5, "round to\nNA bits", fs=7)
    d.wire([pp["r"], rnd["l"]])
    rom = d.mem(6.55, 3.85, 1.45, 0.75, "cos ROM, one\nper harmonic\n2^NA x 16, RAMB18", fs=6.6)
    d.wire([rnd["r"], rom["l"]])
    d.text(6.55, 4.48, "port A: a,  port B: a - 2^(NA-2)", fs=6.8, color=INK2)
    eng = d.block(8.85, 2.85, 1.6, 1.35, "engine\n(any of six)\nL = 2K taps", fs=7.5, fill=BLUE_LIGHT, edge=BLUE)
    d.wire([rom["r"], (7.65, 3.85), (7.65, 3.2), (8.05, 3.2)])
    d.text(7.75, 3.55, "cos, sin\nx K", fs=6.8, color=INK2, ha="left")
    d.wire([sub["r"], (7.65, 2.4), (8.05, 2.4)])
    d.text(7.0, 2.25, "d", fs=8)
    ad = d.op(10.35, 2.85, "+")
    d.wire([(9.65, 2.85), ad["l"]])
    d.text(10.0, 3.05, "e", fs=8)
    ex = d.block(11.6, 2.85, 1.1, 0.5, "exp ROM\n(model)", fs=7, fill=MEM_FILL)
    d.text(10.35, 3.55, "offset", fs=7, color=INK2)
    d.wire([(10.35, 3.42), ad["t"]], color=INK2, lw=1.0)
    d.wire([ad["r"], ex["l"]])
    d.wire([ex["r"], (12.65, 2.85)])
    d.text(13.05, 2.85, "out", fs=8)
    d.note(0.55, 1.3, "Architectures: A1 lms_serial (1 DSP, II = 4K + 3), A2 lms_df (4K DSP, II = 1, D = ceil(log2 2K) "
           "+ 3), A3 time-shared harmonic bank = lms_folded\n(2P DSP, II = ceil(2K/P) + ceil(log2 P) + 5), A4 lattice "
           "IIR notch that tracks the frequency itself (docs/scenarios/A.md).", fs=7.5)
    save(d, "scenario_a.png")


def scen_b():
    d = HwDiagram(13.6, 3.2)
    d.title("Scenario B: bias canceller, the one-weight filter with x = 1 (no multiplier, one sample per clock)")
    d.text(0.6, 2.2, "d", fs=9)
    sub = d.op(3.6, 2.2, "-")
    d.wire([(0.8, 2.2), sub["l"]])
    d.wire([sub["r"], (12.2, 2.2)])
    d.text(12.6, 2.2, "e (output)", fs=8)
    B = d.reg(3.6, 0.95, w=0.75, h=0.5, label="Bacc", fs=7.5)
    vw = d.block(3.6, 1.6, 1.05, 0.38, r"$\gg S$, sat: b", fs=7)
    d.wire([B["t"], vw["b"]])
    d.wire([vw["t"], sub["b"]])
    mx = d.mux(6.6, 1.25, h=1.2, w=0.3)
    d.text(6.6, 2.0, "MODE", fs=7, color=INK2)
    d.wire([(5.2, 2.2), (5.2, 1.55), (6.45, 1.55)], color=INK2, lw=1.0)
    d.text(5.3, 1.7, "e  (LMS)", fs=7, ha="left", color=INK2)
    d.text(5.3, 1.25, r"$\pm 2^{SK}$ (sign)", fs=7, ha="left", color=INK2)
    d.wire([(6.15, 1.25), (6.45, 1.25)], color=INK2, lw=1.0)
    d.text(5.3, 0.85, r"e if $|e|<\tau$ (gated)", fs=7, ha="left", color=INK2)
    d.wire([(6.15, 0.93), (6.45, 0.93)], color=INK2, lw=1.0)
    ad = d.op(8.0, 1.25, "+")
    d.wire([mx["r"], ad["l"]])
    d.wire([ad["b"], (8.0, 0.3), (3.6, 0.3), (3.6, 0.7)], color=INK)
    d.wire([(3.98, 0.95), (4.4, 0.95), (4.4, 0.5), (8.45, 0.5), (8.45, 1.25), ad["r"]], color=INK2, lw=1.0)
    d.text(1.6, 0.95, "first pixel of a row:\nBacc <- d << S", fs=7, color=INK2)
    d.note(8.8, 1.55, "H(z) = (z - 1) / (z - (1 - mu)): a DC blocker.\nThe loop: subtract, add, one register.\n"
           "Sign-error tracks the median of d - b,\ngated adapts on the background only.", fs=7.5)
    save(d, "scenario_b.png")


def scen_c():
    d = HwDiagram(13.6, 4.85)
    d.title("Scenario C: two-band delayed-reference canceller, row by row")
    d.subtitle("HB phase: the Gaussian high band h = z - lowpass(z) of the buffered row (33 taps, 17 multipliers after "
               "the pre-adders). CANCEL phase: the\ncanceller's newest tap is h(refl(t - DELAY)), t = -(L-1) .. W-1: the "
               "V-shaped read order rebuilds the reflected history of the software.")
    d.text(0.55, 2.9, "row\nstream", fs=8)
    z0 = d.mem(1.95, 3.35, 1.3, 0.48, "row buffer 0", fs=7, rows=3)
    z1 = d.mem(1.95, 2.45, 1.3, 0.48, "row buffer 1", fs=7, rows=3)
    d.wire([(0.95, 2.9), (1.15, 2.9), (1.15, 3.35), (1.3, 3.35)], color=INK2, lw=1.0)
    d.wire([(1.15, 2.9), (1.15, 2.45), (1.3, 2.45)], color=INK2, lw=1.0)
    d.text(1.95, 1.95, "ping-pong", fs=7, color=INK2)
    hb = d.region(3.15, 2.15, 4.3, 1.75, "HB phase", color=AQUA)
    w33 = d.block(3.95, 3.0, 1.1, 0.75, "33-tap\nwindow at\nrefl(t)", fs=7)
    d.wire([(2.6, 3.0), w33["l"]])
    fir = d.block(5.45, 3.0, 1.4, 0.75, "17 pre-adders\nx Gaussian Q16\nadder tree, round", fs=6.8, fill=NEUTRAL)
    d.wire([w33["r"], fir["l"]])
    hs = d.op(6.85, 3.0, "-")
    d.wire([fir["r"], hs["l"]])
    d.text(6.85, 3.55, "z", fs=8)
    d.wire([(6.85, 3.42), hs["t"]], color=INK2, lw=1.0)
    hbuf = d.mem(8.3, 3.0, 1.3, 0.75, "h buffer\n(dual port)", fs=7, rows=3)
    d.wire([hs["r"], hbuf["l"]])
    d.region(7.55, 0.4, 5.85, 2.1, "CANCEL phase", color=BLUE, label_pos="tr")
    d.wire([(8.1, 2.62), (8.1, 1.8), (9.05, 1.8)])
    d.wire([(8.5, 2.62), (8.5, 1.2), (9.05, 1.2)])
    eng = d.block(10.25, 1.5, 2.3, 1.2, "engine, L = 128\npipelined: TDL inside\nhandshake: TDL here",
                  fs=7.2, fill=BLUE_LIGHT, edge=BLUE)
    d.text(8.15, 1.95, "port B: x0 = h(refl(t - DELAY))", fs=6.6, ha="left", color=INK2)
    d.text(8.55, 1.35, "port A: d = h(t)", fs=6.6, ha="left", color=INK2)
    d.wire([(1.95, 2.21), (1.95, 0.7), (9.1, 0.7), (9.1, 1.05)], color=INK2, lw=1.0)
    d.text(5.2, 0.55, "p = z(t), the full-band pixel", fs=7, color=INK2)
    d.wire([eng["r"], (12.85, 1.5)])
    d.text(13.05, 1.85, "p - y", fs=8)
    d.note(3.2, 1.75, "row time: (W + 32) + (L - 1 + W x II) cycles\n+ the drain of the pipelined engines", fs=7)
    save(d, "scenario_c.png")


def scen_f():
    d = HwDiagram(13.6, 4.9)
    d.title("Scenario F: reference-sensor canceller (optical-black columns, reference channel)")
    d.subtitle("Each row: NOB optical-black pixels (no light, same offset) then W scene pixels. The OB mean is a shift; "
               "the leave-one-out reference of the\nonline mode is one constant multiply. A tag FIFO drops the outputs "
               "of the OB updates.")
    d.text(0.55, 2.5, "row:\nOB | scene", fs=8)
    ob = d.block(2.2, 3.3, 1.5, 0.55, "OB accumulator\nsum >> log2 NOB", fs=7)
    rf = d.block(2.2, 2.4, 1.5, 0.55, "OB register file\n(NOB words)", fs=7, fill=MEM_FILL)
    d.wire([(1.2, 2.5), (1.35, 2.5), (1.35, 3.3), ob["l"]], color=INK2, lw=1.0)
    d.wire([(1.35, 2.4), rf["l"]], color=INK2, lw=1.0)
    loo = d.block(4.4, 2.4, 1.6, 0.55, r"$(\Sigma - ob_k)\times\frac{1}{NOB-1}$", fs=7.5)
    d.wire([rf["r"], loo["l"]])
    mx = d.mux(6.1, 2.75, h=1.4)
    d.wire([ob["r"], (5.85, 3.3), (5.97, 3.3)])
    d.wire([loo["r"], (5.97, 2.4)])
    d.text(5.6, 1.85, "ref channel", fs=7, color=INK2)
    d.wire([(5.6, 2.0), (5.8, 2.1), (5.97, 2.1)], color=INK2, lw=1.0)
    d.text(6.1, 3.6, "mode", fs=7, color=INK2)
    eng = d.block(7.75, 2.75, 1.6, 1.0, "engine\n1 tap", fs=7.5, fill=BLUE_LIGHT, edge=BLUE)
    d.wire([mx["r"], eng["l"]])
    d.text(7.75, 1.75, "d = scene pixel (or ob_k)", fs=7, color=INK2)
    d.wire([(7.75, 1.9), eng["b"]], color=INK2, lw=1.0)
    tg = d.block(9.65, 2.75, 1.1, 0.6, "tag FIFO", fs=7.2, fill=NEUTRAL)
    d.wire([eng["r"], tg["l"]])
    d.wire([tg["r"], (11.05, 2.75)])
    d.text(11.6, 2.75, "e = scene - w x", fs=8)
    d.note(0.55, 1.35, "mode 0  frozen: out = d - w x_ob (w calibrated before)          F1: one multiplier and a "
           "subtractor\nmode 1  calibrate: adapt on every pixel of a DARK frame    F3: training in blanking or on dark "
           "frames\nmode 2  online: adapt on the OB pixels (leave-one-out), then correct the row frozen   F2", fs=7.4)
    save(d, "scenario_f.png")


def median():
    d = HwDiagram(13.6, 4.6)
    d.title("Baselines: 3 x 3 median and switching median on the same window generator")
    d.subtitle("Nineteen compare-exchange elements (comparator + two multiplexers) find the median of nine "
               "(Paeth's network, as in opt_med9); the switching\nmedian keeps the centre unless it differs from the "
               "median by more than a threshold. No arithmetic beyond comparisons.")
    net = [(1, 2), (4, 5), (7, 8), (0, 1), (3, 4), (6, 7), (1, 2), (4, 5), (7, 8), (0, 3), (5, 8), (4, 7), (3, 6),
           (1, 4), (2, 5), (4, 7), (4, 2), (6, 4), (4, 2)]
    x0, y0, dy, dx = 1.2, 0.5, 0.36, 0.42
    for i in range(9):
        y = y0 + (8 - i) * dy
        d.ax.plot([x0 - 0.3, x0 + len(net) * dx + 0.2], [y, y], color=INK2 if i != 4 else RED, lw=1.0 if i != 4 else 1.6,
                  zorder=2)
        d.text(x0 - 0.45, y, f"p{i}", fs=7, color=INK2)
    for k, (a, b) in enumerate(net):
        x = x0 + k * dx + 0.2
        ya, yb = y0 + (8 - a) * dy, y0 + (8 - b) * dy
        d.ax.plot([x, x], [ya, yb], color=BLUE, lw=1.3, zorder=3)
        for yy in (ya, yb):
            d.dot(x, yy, color=BLUE)
    xe = x0 + len(net) * dx + 0.2
    d.text(xe + 0.55, y0 + 4 * dy, "median", fs=8, color=RED)
    sw = d.block(11.2, 2.0, 2.0, 1.0, "|c - med| > T ?\nmed : c", fs=7.5, fill=NEUTRAL)
    d.wire([(xe + 1.05, y0 + 4 * dy), sw["l"]])
    d.text(11.2, 1.25, "switching median", fs=7.2, color=INK2)
    save(d, "median.png")


# --------------------------------------------------------------------------------- schedules and map
def schedules():
    import matplotlib.pyplot as plt
    from matplotlib.patches import Rectangle
    fig, axs = plt.subplots(4, 1, figsize=(13.6, 8.6), gridspec_kw=dict(hspace=0.75,
                                                                       height_ratios=[1.1, 1.1, 2.0, 1.2]))
    NC = 46

    def bar(ax, x, y, w, col, txt="", fs=7, h=0.7, tc=INK):
        ax.add_patch(Rectangle((x, y - h / 2), w, h, fc=col, ec=INK2, lw=0.6))
        if txt:
            ax.text(x + w / 2, y, txt, ha="center", va="center", fontsize=fs, color=tc)

    def frame(ax, title, rows):
        ax.set_xlim(0, NC)
        ax.set_ylim(-0.6, len(rows) - 0.4)
        ax.set_yticks(range(len(rows)))
        ax.set_yticklabels(rows[::-1], fontsize=7.5)
        ax.set_xticks(range(0, NC + 1, 2))
        ax.tick_params(labelsize=7)
        ax.set_title(title, fontsize=9.5, loc="left", color=INK)
        for sp in ("top", "right"):
            ax.spines[sp].set_visible(False)
        ax.set_xlabel("clock cycle", fontsize=7.5)

    L = 4
    # serial: II = 2L + 3 = 11
    ax = axs[0]
    frame(ax, "lms_serial, L = 4: one multiplier, II = 2L + 3 = 11 (exact LMS)", ["multiplier", "sample"])
    for n in range(4):
        t = n * 11
        bar(ax, t, 0, 1, NEUTRAL, "acc", fs=6)
        bar(ax, t + 1, 1, L, BLUE_LIGHT, f"filter n={n}")
        bar(ax, t + 5, 1, 2, NEUTRAL, "drn, err", fs=6)
        bar(ax, t + 7, 1, L, ORANGE_LIGHT, f"update n={n}")
        bar(ax, t, 0, 11, "white", f"sample {n}", h=0.5)
    # folded: L = 4, P = 2: M = 2, T = 1, II = 8
    ax = axs[1]
    frame(ax, "lms_folded, L = 4, P = 2: II = ceil(L/P) + ceil(log2 P) + 5 = 8; the update of n-1 is fused into the "
              "pass of n", ["lanes", "sample"])
    for n in range(6):
        t = n * 8
        bar(ax, t, 1, 1, NEUTRAL, "acc", fs=6)
        bar(ax, t + 1, 1, 2, BLUE_LIGHT, "pass", fs=6.5)
        bar(ax, t + 3, 1, 5, NEUTRAL, "pipeline, tree, error", fs=6.3)
        bar(ax, t, 0, 8, "white", f"sample {n}", h=0.5)
    # df: reservation table, L = 4: T = 2, D = 5
    ax = axs[2]
    stages = ["F: products", "T1", "T2", "E: error", "U1: e x", "U2: A += g"]
    frame(ax, "lms_df, L = 4 (T = 2): one sample per clock; sample 0's update lands in U2 at cycle 5 and is first "
              "used by sample 6: D = T + 3 = 5", stages)
    for c in range(NC):
        for k, st in enumerate(stages):
            n = c - k
            if 0 <= n < 40:
                col = ORANGE_LIGHT if k >= 4 else (BLUE_LIGHT if k < 3 else NEUTRAL)
                if n == 0 and k == 5:
                    col = ORANGE
                bar(ax, c, len(stages) - 1 - k, 1, col, str(n), fs=6)
    bar(ax, 6, len(stages) - 1, 1, BLUE, "6", fs=6, tc="white")
    ax.annotate("", xy=(6.5, len(stages) - 1.4), xytext=(5.5, 0.4),
                arrowprops=dict(arrowstyle="-|>", color=RED, lw=1.2))
    # rowblock: rows of 8 samples, drain T + 4 = 6, commit
    ax = axs[3]
    frame(ax, "lms_rowblock, L = 4, rows of N = 8 (illustration): weights frozen in a row; the drain of T + 4 = 6 steps "
              "lets the last gradient in, then A += G", ["engine", "row"])
    t = 0
    for r in range(3):
        bar(ax, t, 0, 8, "white", f"row {r}", h=0.5)
        for j in range(8):
            bar(ax, t + j, 1, 1, AQUA_LIGHT, str(j), fs=6)
        bar(ax, t + 8, 1, 6, NEUTRAL, "drain", fs=6.5)
        bar(ax, t + 13, 1, 1, AQUA, "", fs=6)
        ax.text(t + 13.5, 1.55, "commit", fontsize=6.5, ha="center", color=AQUA)
        t += 15
    fig.savefig(OUT / "schedules.png", dpi=170, bbox_inches="tight")
    plt.close(fig)
    print("wrote figures/diagrams/schedules.png", flush=True)


def verification():
    d = HwDiagram(14.4, 5.6)
    d.title("Verification: one model, two implementations, every output word compared")
    d.subtitle("Images are scored on the floating-point algorithm and on the bit-accurate models; the Verilog tops and the "
               "HLS C++ tops must reproduce the models word for word.")
    y = 3.05
    fl = d.block(1.75, y, 2.8, 1.15, "floating point\nafarch/reference.py\nthe algorithms of the\ncompanion repository",
                 fs=7.6, fill=NEUTRAL)
    md = d.block(6.05, y, 3.3, 1.15, "bit-accurate models\nafarch/fxp.py, engines.py,\nfrontends.py, scenarios.py\n"
                 "one model per class: exact, delayed, block", fs=7.6, fill=BLUE_LIGHT, edge=BLUE)
    rt = d.block(12.05, 3.85, 3.2, 0.95, "RTL, Verilog-2005\nrtl/engines, rtl/scenarios, rtl/baselines", fs=7.6,
                 fill=ORANGE_LIGHT, edge=ORANGE)
    hl = d.block(12.05, 2.2, 3.2, 0.95, "HLS C++\nhls/include/afhls, hls/src (Vitis HLS style)", fs=7.6,
                 fill=AQUA_LIGHT, edge=AQUA)
    d.wire([fl["r"], md["l"]], color=INK2)
    d.text(3.92, y + 0.2, "same scenes", fs=7, color=INK2)
    d.text(3.92, y - 0.22, "PSNR, SSIM", fs=7, color=INK2)
    d.wire([(md["r"][0], y + 0.25), (9.15, y + 0.25), (9.15, 3.95), (rt["l"][0], 3.95)], color=INK)
    d.wire([(rt["l"][0], 3.72), (9.35, 3.72), (9.35, y + 0.1), (md["r"][0], y + 0.1)], color=INK)
    d.wire([(md["r"][0], y - 0.12), (9.35, y - 0.12), (9.35, 2.36), (hl["l"][0], 2.36)], color=INK)
    d.wire([(hl["l"][0], 2.1), (9.15, 2.1), (9.15, y - 0.27), (md["r"][0], y - 0.27)], color=INK)
    d.note(9.25, 4.3, "Icarus Verilog -g2005 -Wall", fs=7.0, color=INK2)
    d.note(9.25, 1.95, "g++ C simulation:\nint64 or ap_int<W>", fs=7.0, color=INK2)
    d.text(10.43, y + 0.02, "every output\nword equal", fs=7.2, color=RED)
    ex = d.block(6.05, 0.95, 3.3, 0.75, "experiments/*.py: delay, step, word length,\n18 application examples, "
                 "algorithm figures", fs=7.0, fill="white")
    d.wire([md["b"], ex["t"]], color=INK2, lw=1.0)
    ys = d.block(12.05, 5.0, 3.2, 0.5, "Yosys synth_xilinx: DSP, LUT, FF, SRL, RAM", fs=7.0, fill="white")
    d.wire([rt["t"], ys["b"]], color=INK2, lw=1.0)
    vh = d.block(12.05, 0.95, 3.2, 0.75, "Vitis HLS: csim, csynth, cosim, export\nhls/scripts/run_vitis_hls.tcl",
                 fs=7.0, fill="white")
    d.wire([hl["b"], vh["t"]], color=INK2, lw=1.0)
    d.note(0.3, 2.1, "sim/test_engines.py   24 engine cases + 8 measured II\n"
           "sim/test_scenarios.py   32 scenario-top cases\n"
           "smoke/smoke.py   17 cases, A to F, RTL and HLS\n"
           "experiments/examples_hw.py   18 examples:\n"
           "   HLS on the whole frame, RTL on the frame,\n"
           "   a strip (C) or a tile (D, E)", fs=7.0)
    save(d, "verification.png")


def hls_structure():
    d = HwDiagram(14.6, 7.3)
    d.title("HLS C++: the three algorithmic classes as templates, the scenario tops as streams")
    d.subtitle("Every signal has the width of its RTL counterpart (ap_int<W>); every narrowing goes through sat<W>() or "
               "narrow<W>(), so 64-bit C simulation and ap_int give the same words as the models.")
    # headers
    hx, hw_ = 1.75, 2.9
    hdr = [("types.h", "sint<W>, sat<W>, narrow<W>\nap_int or int64 (AFHLS_AP_TYPES)"),
           ("arith.h", "Fxp<S, RULE, LEAK>: the arithmetic\ncontract; Gate; ErrUnit"),
           ("engines.h", "exact_step, delayed_step,\ndelayed_step_tdl, block_step"),
           ("engine_select.h", "ENGINE 0..5 -> class, D,\nstate arrays and their pragmas")]
    d.text(hx, 5.95, "hls/include/afhls/", fs=8, color=INK2)
    for k, (n, t) in enumerate(hdr):
        yy = 5.35 - k * 1.05
        d.block(hx, yy, hw_, 0.85, f"{n}\n{t}", fs=7.0, fill="white")
    # classes
    cx = 6.4
    d.text(cx, 5.95, "the three classes (engines.h)", fs=8, color=INK2)
    cls = [(BLUE, BLUE_LIGHT, "exact LMS  (ENGINE 0, 1)",
            "one pass per pixel: FUSED loop over ceil(L/P)\nPIPELINE II=1, P lanes UNROLL; the pending\n"
            "update of n-1 is applied in the same pass"),
           (ORANGE, ORANGE_LIGHT, "delayed LMS  (ENGINE 2, 3)",
            "one pixel per clock: PIPELINE II=1\nL filter + L update multipliers; a D-slot\n"
            "shift register holds (adapt, e, taps)"),
           (AQUA, AQUA_LIGHT, "block LMS  (ENGINE 4, 5)",
            "one pixel per clock: PIPELINE II=1\nweights frozen along the row, G[L] sums\n"
            "the gradients, the row's last pixel commits")]
    for k, (ec, fc, h, t) in enumerate(cls):
        yy = 5.1 - k * 1.45
        d.block(cx, yy, 4.0, 1.2, f"{h}\n{t}", fs=7.1, fill=fc, edge=ec)
    # tops
    tx = 11.75
    d.text(tx, 5.95, "scenario tops (hls/src), AXI4-Stream + AXI4-Lite", fs=8, color=INK2)
    tops = [("scen_a_top", "phase accumulators, a cos ROM per harmonic"),
            ("scen_b_top", "bias loop, no multiplier"),
            ("scen_c_top", "Gaussian high band, tapped delay line"),
            ("scen_de_top", "2R+2 line buffers, reflected window"),
            ("scen_f_top", "OB mean, leave-one-out, modes 0/1/2")]
    for k, (n, t) in enumerate(tops):
        yy = 5.4 - k * 0.82
        d.block(tx, yy, 4.6, 0.66, f"{n}: {t}", fs=7.1, fill="white")
    d.region(hx - hw_ / 2 - 0.12, 1.45, hw_ + 0.24, 4.4, "", color=MUTED)
    d.region(cx - 2.12, 1.45, 4.24, 4.4, "", color=MUTED)
    d.region(tx - 2.42, 1.45, 4.84, 4.4, "", color=MUTED)
    d.wire([(hx + hw_ / 2 + 0.12, 3.72), (cx - 2.12, 3.72)], color=INK2, lw=1.4)
    d.text((hx + hw_ / 2 + cx - 2.0) / 2, 3.95, "included by", fs=7, color=INK2)
    d.wire([(cx + 2.12, 3.72), (tx - 2.42, 3.72)], color=INK2, lw=1.4)
    d.text((cx + 2.12 + tx - 2.42) / 2, 4.0, "ENGINE\nselects one", fs=7, color=INK2)
    # flows
    fy = 0.75
    d.block(4.0, fy, 6.6, 0.8, "C simulation: hls/tb/tb_scen_*.cpp + hls/csim/hls_stream.h, g++ -std=c++14\n"
            "smoke/smoke.py (every scenario), experiments/examples_hw.py (every example, whole frames)", fs=7.1,
            fill=NEUTRAL)
    d.block(11.1, fy, 6.0, 0.8, "Vitis HLS: hls/scripts/run_vitis_hls.tcl <case> csim | syn | cosim | export\n"
            "smoke/run_vitis.sh: every smoke case, co-simulation compared word for word", fs=7.1, fill=NEUTRAL)
    save(d, "hls_structure.png")


def architecture_map():
    import matplotlib.pyplot as plt
    from matplotlib.patches import FancyBboxPatch
    from afarch.cost import model
    cols = ["serial", "folded", "df", "systolic", "rowblock", "da", "dedicated"]
    colhead = ["lms_serial\nexact LMS", "lms_folded\nexact LMS", "lms_df\ndelayed LMS", "lms_systolic\ndelayed LMS",
               "lms_rowblock\nblock LMS", "lms_da\nblock LMS", "dedicated\nstructure"]
    ccol = {"serial": BLUE_LIGHT, "folded": BLUE_LIGHT, "df": ORANGE_LIGHT, "systolic": ORANGE_LIGHT,
            "rowblock": AQUA_LIGHT, "da": AQUA_LIGHT, "dedicated": "#e9e5fb"}
    rows = [("A", "adaptive notch\nL = 2K (K = 2)", 4, {"serial": "A1", "folded": "A3", "df": "A2"},
             {"dedicated": "A4  lattice IIR notch\nfrequency tracking"}, 2),
            ("B", "bias / drift\none weight, x = 1", None, {}, {"dedicated": "B1 LMS, B2 sign-error,\nB3 gated: no DSP, II 1"},
             None),
            ("C", "delayed reference\nL = 128", 128, {"serial": "C1", "folded": "C2", "df": "C3", "systolic": "C3'",
                                                     "rowblock": "C4", "da": "C5"}, {}, 8),
            ("D", "self-tuning (blind spot)\nL = 24", 24, {"serial": "D1", "folded": "D2", "df": "D3",
                                                          "systolic": "D4", "rowblock": "D5"},
             {"dedicated": "median 3 x 3,\nswitching median"}, 6),
            ("E", "line enhancer\nL = 48", 48, {"serial": "E1", "folded": "E2", "df": "E3", "systolic": "E4",
                                               "rowblock": "E5"}, {}, 12),
            ("F", "reference sensor\none tap", 1, {"serial": "F1-F3"}, {"dedicated": "F1 frozen, F2 OB online,\n"
                                                                                  "F3 dark-frame calibration"}, None)]
    fig = plt.figure(figsize=(14.5, 7.0))
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, 14.5)
    ax.set_ylim(0, 7.0)
    ax.axis("off")
    ax.text(0.15, 6.85, "25 architectures for six scenarios on six engines (C3 in two forms): code, multipliers, "
            "cycles per sample II, adaptation delay D", fontsize=11.5, fontweight="bold", va="top", color=INK)
    x0, w0, cw, rh, y0 = 0.15, 2.05, 1.75, 0.86, 5.95
    for j, h in enumerate(colhead):
        ax.text(x0 + w0 + (j + 0.5) * cw, y0 + 0.28, h, ha="center", va="center", fontsize=8, color=INK)
    for i, (sc_, name, L, codes, ded, P) in enumerate(rows):
        y = y0 - (i + 1) * rh
        ax.text(x0 + 0.05, y + rh / 2, sc_, fontsize=15, fontweight="bold", va="center", color=INK)
        ax.text(x0 + 0.42, y + rh / 2, name, fontsize=7.6, va="center", color=INK2)
        for j, c in enumerate(cols):
            xc = x0 + w0 + j * cw
            txt, fill = "", "white"
            if c in codes and L:
                m = model(c, L, P=P or 1)
                dsp = m["mult"]
                ii = m["II"]
                dd = f", D {m['D']}" if m["D"] else ""
                extra = f"P = {P}\n" if c == "folded" else ""
                txt = f"{codes[c]}\n{extra}{dsp} mult, II {ii}{dd}"
                fill = ccol[c]
            elif c in ded:
                txt, fill = ded[c], ccol[c]
            elif L and c != "dedicated":
                m = model(c, L, P=P or 1)
                txt = f"(works: {m['mult']} mult,\nII {m['II']})"
                fill = "#fafaf8"
            ax.add_patch(FancyBboxPatch((xc + 0.04, y + 0.05), cw - 0.08, rh - 0.1,
                                        boxstyle="round,pad=0,rounding_size=0.06", fc=fill, ec="#d0cfc8", lw=0.8))
            if txt:
                ax.text(xc + cw / 2, y + rh / 2, txt, ha="center", va="center", fontsize=7.0,
                        color=INK if fill != "#fafaf8" else MUTED, linespacing=1.25)
    ax.text(0.15, 0.12, "Every engine is RTL in rtl/engines and runs in the tops of A, C, D, E and F (lms_engine, "
            "ENGINE = 0..5); grey cells work but are not the natural choice. B has its own multiplier-free datapath.\n"
            "A4 is a floating-point model (afarch/lattice.py). II = clock cycles per sample; multipliers map one-to-one "
            "onto DSP48E1 slices; D = adaptation delay in samples.", fontsize=7.8, color=INK2, va="bottom")
    fig.savefig(OUT / "architecture_map.png", dpi=170)
    plt.close(fig)
    print("wrote figures/diagrams/architecture_map.png", flush=True)

if __name__ == "__main__":
    which = sys.argv[1:]
    for name, fn in list(globals().items()):
        if callable(fn) and fn.__module__ == "__main__" and not name.startswith("_") and name not in ("save",):
            if not which or name in which:
                fn()
