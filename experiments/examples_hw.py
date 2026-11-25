"""The application examples through the HLS C++ tops and the Verilog tops, word for word against the models.

    python experiments/examples_hw.py                  # every example (about an hour, most of it Icarus)
    python experiments/examples_hw.py A.2 D            # some examples, or all of a scenario (rows replaced)
    python experiments/examples_hw.py --no-rtl         # HLS only (seconds per configuration)
    python experiments/examples_hw.py --ap-types DIR   # the HLS tops with exact-width ap_int types

Every configuration of experiments/example_defs.py goes through the model (afarch), the HLS top (hls/, a g++ C
simulation) over the whole frame and, where it is marked rtl, through the Verilog top (rtl/, Icarus Verilog).
Every output word of a top must equal the model's: the pixels, and the gate flags of D or the bias track of B.
Icarus simulates the wide engines slowly (about 400 pixels per second for the 24-tap direct-form engine of D), so
the RTL runs of C stream a 32-row strip of the example and those of D and E a tile; A, B and F stream the whole
frame. Writes results/examples_hw.csv.
"""
import sys
import time

import numpy as np

from common import write_csv, read_csv, RESULTS
from example_defs import build, run, score, select
from afarch import hdl


def subscene(s, rows, cols):
    """The part of a scene that one RTL run streams (2-D planes cropped, per-row data cut to the rows)."""
    H, W = s["clean"].shape
    out = {}
    for k, v in s.items():
        if isinstance(v, np.ndarray) and v.ndim == 2 and v.shape == (H, W):
            out[k] = v[rows, cols]
        elif isinstance(v, np.ndarray) and v.ndim >= 1 and v.shape[0] == H:
            out[k] = v[rows]
        else:
            out[k] = v
    return out


def region(e, rows, cols, H, W):
    r0, r1, _ = rows.indices(H)
    c0, c1, _ = cols.indices(W)
    if (r1 - r0, c1 - c0) == (H, W):
        return f"full frame {W} x {H}"
    if c1 - c0 == W:
        return f"rows {r0}-{r1 - 1} ({W} x {r1 - r0})"
    return f"tile {c1 - c0} x {r1 - r0} at row {r0}, column {c0}"


def rank(exs, r):
    """Csv order: example, then its configurations in definition order, HLS before RTL."""
    ids = list(exs)
    labels = [c.label for c in exs[r["example"]].configs]
    return (ids.index(r["example"]), labels.index(r["config"]) if r["config"] in labels else 99,
            0 if r["impl"] == "HLS C++" else 1)


def main(argv):
    sel, ap, do_rtl = [], None, True
    it = iter(argv)
    for a in it:
        if a == "--ap-types":
            ap = next(it)
        elif a == "--no-rtl":
            do_rtl = False
        else:
            sel.append(a)
    if do_rtl and not hdl.have_iverilog():
        print("iverilog not found: HLS only")
        do_rtl = False
    exs = build()
    sel = select(list(exs), sel) or list(exs)
    impls = {"HLS C++"} | ({"RTL"} if do_rtl else set())
    keep = [r for r in (read_csv("examples_hw.csv") if (RESULTS / "examples_hw.csv").exists() else [])
            if r["example"] not in sel or r["impl"] not in impls]           # rows this run does not redo
    rows = list(keep)
    allok = True
    for eid in sel:
        e = exs[eid]
        s = e.scene()
        H, W = s["clean"].shape
        for c in e.configs:
            todo = [("hls", slice(None), slice(None))] if c.hls else []
            if do_rtl and c.rtl:
                todo.append(("rtl", e.rtl_rows, e.rtl_cols))
            for impl, rr, cc in todo:
                part = s if (rr, cc) == (slice(None), slice(None)) else subscene(s, rr, cc)
                t0 = time.time()
                img_m, raw_m = run(e, part, c, "model")
                t1 = time.time()
                img_i, raw_i = run(e, part, c, impl, ap_types=ap)
                t2 = time.time()
                raw_m, raw_i = np.asarray(raw_m, np.int64), np.asarray(raw_i, np.int64)
                ok = raw_m.shape == raw_i.shape and np.array_equal(raw_m, raw_i)
                allok &= ok
                pm, _ = score(e, part["clean"], img_m)
                pi, _ = score(e, part["clean"], img_i)
                rows.append(dict(example=eid, config=c.label, cls=c.cls, impl="HLS C++" if impl == "hls" else "RTL",
                                 region=region(e, rr, cc, H, W), words=int(len(raw_m)), match=bool(ok),
                                 psnr_model=round(pm, 3), psnr_impl=round(pi, 3),
                                 seconds_model=round(t1 - t0, 1), seconds_impl=round(t2 - t1, 1),
                                 ap_int=bool(ap) if impl == "hls" else ""))
                print(rows[-1], flush=True)
                rows.sort(key=lambda r: rank(exs, r))
                write_csv("examples_hw.csv", rows)
    print("ALL MATCH" if allok else "MISMATCHES")
    return 0 if allok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
