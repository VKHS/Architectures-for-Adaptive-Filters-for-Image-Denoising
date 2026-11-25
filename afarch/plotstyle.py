"""Shared figure style: colours, fonts, and small drawing helpers for block diagrams."""
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt                       # noqa: E402
from matplotlib.patches import FancyBboxPatch, Circle, Rectangle   # noqa: E402

# categorical slots, fixed order
BLUE, ORANGE, AQUA, YELLOW, MAGENTA, GREEN, VIOLET, RED = (
    "#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948")
SERIES = [BLUE, ORANGE, AQUA, YELLOW, MAGENTA, GREEN, VIOLET, RED]
INK, INK2, MUTED = "#0b0b0b", "#52514e", "#898781"
GRID, AXIS, SURFACE, NEUTRAL = "#e1e0d9", "#c3c2b7", "#fcfcfb", "#f0efec"
BLUE_LIGHT, ORANGE_LIGHT, AQUA_LIGHT = "#cde2fb", "#fbe0d4", "#d1efe3"


def setup():
    plt.rcParams.update({
        "font.family": "DejaVu Sans",
        "font.size": 9,
        "axes.titlesize": 9.5,
        "axes.labelsize": 9,
        "axes.edgecolor": AXIS,
        "axes.linewidth": 0.8,
        "axes.labelcolor": INK2,
        "axes.titlecolor": INK,
        "axes.grid": False,
        "grid.color": GRID,
        "grid.linewidth": 0.8,
        "grid.linestyle": "-",
        "xtick.color": MUTED,
        "ytick.color": MUTED,
        "xtick.labelcolor": INK2,
        "ytick.labelcolor": INK2,
        "xtick.labelsize": 8,
        "ytick.labelsize": 8,
        "legend.frameon": False,
        "legend.fontsize": 8,
        "lines.linewidth": 2.0,
        "lines.solid_capstyle": "round",
        "lines.solid_joinstyle": "round",
        "figure.facecolor": "white",
        "axes.facecolor": "white",
        "savefig.facecolor": "white",
        "savefig.dpi": 150,
        "mathtext.fontset": "dejavusans",
    })


def clean_axes(ax, grid_y=True, grid_x=False):
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    if grid_y:
        ax.yaxis.grid(True)
    if grid_x:
        ax.xaxis.grid(True)
    ax.set_axisbelow(True)


def panel_label(ax, s, x=-0.02, y=1.02):
    ax.text(x, y, s, transform=ax.transAxes, fontsize=10, fontweight="bold", color=INK, ha="right", va="bottom")


def show_image(ax, img, title=None, vmin=0, vmax=1, cmap="gray"):
    ax.imshow(img, cmap=cmap, vmin=vmin, vmax=vmax, interpolation="nearest")
    ax.set_xticks([])
    ax.set_yticks([])
    for s in ax.spines.values():
        s.set_visible(False)
    if title:
        ax.set_title(title, fontsize=8.5, color=INK, pad=3)


# --------------------------------------------------------------------------------------- block diagrams
class Diagram:
    """Minimal signal-flow diagram on a data-coordinate canvas (units ~ inches)."""

    def __init__(self, width, height, title=None):
        self.fig = plt.figure(figsize=(width, height))
        self.ax = self.fig.add_axes([0, 0, 1, 1])
        self.ax.set_xlim(0, width)
        self.ax.set_ylim(0, height)
        self.ax.set_aspect("equal")
        self.ax.axis("off")
        if title:
            self.ax.text(0.15, height - 0.18, title, fontsize=11, fontweight="bold", color=INK, va="top")

    def block(self, x, y, w, h, text, fill=NEUTRAL, edge=INK2, fs=9, lw=1.1, tc=INK):
        self.ax.add_patch(FancyBboxPatch((x - w / 2, y - h / 2), w, h, boxstyle="round,pad=0,rounding_size=0.06",
                                         fc=fill, ec=edge, lw=lw, zorder=3))
        if text:
            self.ax.text(x, y, text, ha="center", va="center", fontsize=fs, color=tc, zorder=4, linespacing=1.25)
        return dict(l=(x - w / 2, y), r=(x + w / 2, y), t=(x, y + h / 2), b=(x, y - h / 2), c=(x, y))

    def adaptive(self, x, y, w, h, text, fill="white", fs=9):
        """Adaptive filter: a block crossed by the diagonal 'adjustable' arrow; the label sits on top."""
        p = self.block(x, y, w, h, None, fill=fill, fs=fs)
        self.ax.annotate("", xy=(x + w / 2 + 0.12, y + h / 2 + 0.12), xytext=(x - w / 2 - 0.08, y - h / 2 - 0.12),
                         arrowprops=dict(arrowstyle="-|>", color=MUTED, lw=0.9, mutation_scale=9, shrinkA=0, shrinkB=0),
                         zorder=5)
        self.ax.text(x, y, text, ha="center", va="center", fontsize=fs, color=INK, zorder=6, linespacing=1.25,
                     bbox=dict(boxstyle="round,pad=0.12", fc=fill, ec="none"))
        return p

    def sum(self, x, y, r=0.2, signs=None, fs=8.5):
        self.ax.add_patch(Circle((x, y), r, fc="white", ec=INK2, lw=1.1, zorder=3))
        self.ax.text(x, y, r"$\Sigma$", ha="center", va="center", fontsize=fs + 1, color=INK, zorder=4)
        offs = dict(l=(-r - 0.1, r * 0.55), t=(r * 0.55, r + 0.08), b=(r * 0.55, -r - 0.12), r=(r + 0.1, r * 0.55))
        for side, s in (signs or {}).items():
            dx, dy = offs[side]
            self.ax.text(x + dx, y + dy, s, ha="center", va="center", fontsize=fs + 1, color=INK, fontweight="bold")
        return dict(l=(x - r, y), r=(x + r, y), t=(x, y + r), b=(x, y - r), c=(x, y))

    def wire(self, pts, color=INK, lw=1.3, head=True, ls="-"):
        for a, b in zip(pts[:-2], pts[1:-1]):
            self.ax.plot([a[0], b[0]], [a[1], b[1]], color=color, lw=lw, ls=ls, solid_capstyle="butt", zorder=2)
        a, b = pts[-2], pts[-1]
        if head:
            self.ax.annotate("", xy=b, xytext=a, arrowprops=dict(arrowstyle="-|>", color=color, lw=lw, ls=ls,
                                                                 mutation_scale=10, shrinkA=0, shrinkB=0), zorder=2)
        else:
            self.ax.plot([a[0], b[0]], [a[1], b[1]], color=color, lw=lw, ls=ls, zorder=2)

    def dot(self, x, y, color=INK):
        self.ax.add_patch(Circle((x, y), 0.035, fc=color, ec=color, zorder=4))

    def text(self, x, y, s, fs=9, color=INK, ha="center", va="center", **kw):
        self.ax.text(x, y, s, fontsize=fs, color=color, ha=ha, va=va, zorder=6, **kw)

    def note(self, x, y, s, fs=8, color=INK2, ha="left", va="top", **kw):
        self.ax.text(x, y, s, fontsize=fs, color=color, ha=ha, va=va, zorder=6, linespacing=1.35, **kw)

    def rect(self, x0, y0, w, h, fc, ec="none", lw=0.0, z=1, alpha=1.0):
        self.ax.add_patch(Rectangle((x0, y0), w, h, fc=fc, ec=ec, lw=lw, zorder=z, alpha=alpha))

    def save(self, path, margin=24):
        """Save at 170 dpi and crop the white border to ``margin`` pixels around the drawing."""
        self.fig.savefig(path, dpi=170)
        plt.close(self.fig)
        import numpy as np
        from PIL import Image
        im = Image.open(path).convert("RGB")
        a = np.asarray(im)
        ink = np.nonzero((a < 245).any(axis=2))
        if len(ink[0]):
            y0, y1 = max(ink[0].min() - margin, 0), min(ink[0].max() + margin + 1, a.shape[0])
            x0, x1 = max(ink[1].min() - margin, 0), min(ink[1].max() + margin + 1, a.shape[1])
            im.crop((x0, y0, x1, y1)).save(path)


# ------------------------------------------------------------------------------------ hardware diagrams
from matplotlib.patches import Polygon, FancyArrowPatch                           # noqa: E402

MEM_FILL, REG_FILL, DSP_FILL = "#fff4d6", "#ffffff", "#e8f1fc"
CLS_COLOR = {"exact": BLUE, "delayed": ORANGE, "block": AQUA, "bias": VIOLET, "front": INK2}


class HwDiagram(Diagram):
    """Signal-flow canvas with register-transfer symbols: registers, multipliers, adders, multiplexers,
    memories, buses and dashed regions (DSP slices, lanes, cells)."""

    def reg(self, x, y, w=0.34, h=0.42, label="", fs=7.5, fill=REG_FILL, edge=INK):
        """Clocked register: a box with the clock wedge on its lower edge; (x, y) is the centre."""
        self.ax.add_patch(Rectangle((x - w / 2, y - h / 2), w, h, fc=fill, ec=edge, lw=1.1, zorder=3))
        self.ax.add_patch(Polygon([(x - 0.07, y - h / 2), (x + 0.07, y - h / 2), (x, y - h / 2 + 0.09)],
                                  closed=True, fc="none", ec=edge, lw=0.8, zorder=4))
        if label:
            self.ax.text(x, y + 0.03, label, ha="center", va="center", fontsize=fs, color=INK, zorder=5)
        return dict(l=(x - w / 2, y), r=(x + w / 2, y), t=(x, y + h / 2), b=(x, y - h / 2), c=(x, y))

    def op(self, x, y, sym, r=0.17, fill="white", edge=INK2, fs=11):
        """Arithmetic operator in a circle: sym = 'x', '+', '-' ..."""
        self.ax.add_patch(Circle((x, y), r, fc=fill, ec=edge, lw=1.1, zorder=3))
        t = {"x": r"$\times$", "+": "+", "-": r"$-$", "s": r"$\Sigma$"}.get(sym, sym)
        self.ax.text(x, y - 0.01, t, ha="center", va="center", fontsize=fs, color=INK, zorder=4)
        return dict(l=(x - r, y), r=(x + r, y), t=(x, y + r), b=(x, y - r), c=(x, y))

    def mux(self, x, y, h=0.7, w=0.26, label="", fs=7, flip=False):
        """Multiplexer: a trapezoid, inputs on the left (right if flip)."""
        s = -1 if flip else 1
        pts = [(x - s * w / 2, y - h / 2), (x - s * w / 2, y + h / 2), (x + s * w / 2, y + h / 2 - 0.12),
               (x + s * w / 2, y - h / 2 + 0.12)]
        self.ax.add_patch(Polygon(pts, closed=True, fc="white", ec=INK2, lw=1.1, zorder=3))
        if label:
            self.ax.text(x, y, label, ha="center", va="center", fontsize=fs, color=INK, zorder=4, rotation=90)
        return dict(l=(x - s * w / 2, y), r=(x + s * w / 2, y), t=(x, y + h / 2 - 0.06), b=(x, y - h / 2 + 0.06),
                    c=(x, y))

    def mem(self, x, y, w, h, label, fs=8, fill=MEM_FILL, rows=4):
        """Memory (RAM/ROM): a box with word lines."""
        self.ax.add_patch(Rectangle((x - w / 2, y - h / 2), w, h, fc=fill, ec=INK2, lw=1.1, zorder=3))
        for k in range(1, rows):
            yy = y - h / 2 + k * h / rows
            self.ax.plot([x - w / 2 + 0.05, x - w / 2 + 0.16], [yy, yy], color=MUTED, lw=0.6, zorder=4)
        self.ax.text(x + 0.05, y, label, ha="center", va="center", fontsize=fs, color=INK, zorder=5, linespacing=1.2)
        return dict(l=(x - w / 2, y), r=(x + w / 2, y), t=(x, y + h / 2), b=(x, y - h / 2), c=(x, y))

    def region(self, x0, y0, w, h, label="", color=BLUE, fs=7.5, fill=None, ls="--", label_pos="tl"):
        """Dashed grouping rectangle (DSP slice, lane, systolic cell, clock domain...)."""
        self.ax.add_patch(FancyBboxPatch((x0, y0), w, h, boxstyle="round,pad=0,rounding_size=0.08",
                                         fc=fill if fill else "none", ec=color, lw=1.0, ls=ls, zorder=1))
        if label:
            if label_pos == "tl":
                self.ax.text(x0 + 0.08, y0 + h - 0.08, label, ha="left", va="top", fontsize=fs, color=color, zorder=6)
            elif label_pos == "bl":
                self.ax.text(x0 + 0.08, y0 + 0.07, label, ha="left", va="bottom", fontsize=fs, color=color, zorder=6)
            elif label_pos == "tr":
                self.ax.text(x0 + w - 0.08, y0 + h - 0.08, label, ha="right", va="top", fontsize=fs, color=color,
                             zorder=6)
            else:
                self.ax.text(x0 + w - 0.08, y0 + 0.07, label, ha="right", va="bottom", fontsize=fs, color=color,
                             zorder=6)

    def bus(self, pts, label=None, color=INK, lw=2.2, head=True, at=0.5, fs=6.5, ls="-"):
        """Multi-bit bus: a thick wire with a slash and its width."""
        self.wire(pts, color=color, lw=lw, head=head, ls=ls)
        if label:
            a, b = pts[0], pts[1]
            mx, my = a[0] + at * (b[0] - a[0]), a[1] + at * (b[1] - a[1])
            self.ax.plot([mx - 0.06, mx + 0.06], [my - 0.08, my + 0.08], color=color, lw=1.0, zorder=5)
            horiz = abs(b[1] - a[1]) < abs(b[0] - a[0])
            if horiz:
                self.ax.text(mx, my + 0.1, label, ha="center", va="bottom", fontsize=fs, color=INK2, zorder=6)
            else:
                self.ax.text(mx + 0.1, my, label, ha="left", va="center", fontsize=fs, color=INK2, zorder=6)

    def curved(self, a, b, rad=0.3, color=INK, lw=1.2, ls="-"):
        self.ax.add_patch(FancyArrowPatch(a, b, connectionstyle=f"arc3,rad={rad}", arrowstyle="-|>",
                                          mutation_scale=10, color=color, lw=lw, ls=ls, zorder=2))

    def title(self, s, fs=11.5):
        self.ax.text(0.15, self.ax.get_ylim()[1] - 0.15, s, fontsize=fs, fontweight="bold", color=INK, va="top")

    def subtitle(self, s, y=None, fs=8.5):
        self.ax.text(0.15, (self.ax.get_ylim()[1] - 0.5) if y is None else y, s, fontsize=fs, color=INK2, va="top",
                     linespacing=1.35)
