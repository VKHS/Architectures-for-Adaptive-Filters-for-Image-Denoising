"""Shared paths and helpers of the experiment scripts."""
import csv
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from afarch.plotstyle import setup                                                     # noqa: E402

RESULTS = REPO / "results"
FIG = REPO / "figures"
RESULTS.mkdir(exist_ok=True)
setup()


def write_csv(name, rows, fields=None):
    fields = fields or list(rows[0].keys())
    with open(RESULTS / name, "w", newline="") as f:
        w = csv.DictWriter(f, fields)
        w.writeheader()
        w.writerows(rows)
    print("wrote", f"results/{name}", flush=True)


def read_csv(name):
    with open(RESULTS / name) as f:
        return list(csv.DictReader(f))


def save(fig, sub, name, dpi=170):
    out = FIG / sub
    out.mkdir(parents=True, exist_ok=True)
    fig.savefig(out / name, dpi=dpi, bbox_inches="tight")
    import matplotlib.pyplot as plt
    plt.close(fig)
    print("wrote", f"figures/{sub}/{name}", flush=True)


class Timer:
    def __init__(self):
        self.t0 = time.time()

    def __str__(self):
        return f"{time.time() - self.t0:.0f} s"
