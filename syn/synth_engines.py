"""Yosys synth_xilinx (xc7) cell counts of the six engines over the tap counts of the scenarios.

    python syn/synth_engines.py          # writes results/synth_engines.csv
    python syn/synth_engines.py --smoke  # every engine at L = 8: synthesizes, prints the counts, writes nothing

L = 2 is scenario A (one harmonic), 24 is D (5 x 5 blind spot), 48 is E (7 x 7), 128 is C (with the tapped
delay line inside the pipelined engines, TDL = 1).
"""
import csv
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from afarch import synth                                                  # noqa: E402
from afarch.hdl import REPO                                               # noqa: E402

CONFIGS = [
    ("serial", 2, {}), ("serial", 24, {}), ("serial", 48, {}), ("serial", 128, {}),
    ("folded", 24, dict(P=2)), ("folded", 24, dict(P=6)), ("folded", 48, dict(P=12)),
    ("folded", 128, dict(P=8)), ("folded", 128, dict(P=32)),
    ("df", 2, {}), ("df", 24, {}), ("df", 48, {}), ("df", 128, dict(TDL=1)),
    ("systolic", 2, {}), ("systolic", 24, {}), ("systolic", 48, {}), ("systolic", 24, dict(TDL=1)),
    ("systolic", 128, dict(TDL=1)),
    ("rowblock", 24, {}), ("rowblock", 48, {}), ("rowblock", 128, dict(TDL=1)),
    ("da", 24, {}), ("da", 48, {}), ("da", 128, {}),
]
FIELDS = ["engine", "L", "P", "TDL", "DSP48E1", "LUT", "FF", "SRL", "LUTRAM", "RAMB18", "RAMB36", "CARRY4", "MUXF",
          "seconds"]


SMOKE = [("serial", 8, {}, 1), ("folded", 8, dict(P=2), 4), ("df", 8, {}, 16), ("systolic", 8, {}, 16),
         ("rowblock", 8, {}, 16), ("da", 8, {}, 0)]


def smoke():
    """Synthesis check for CI: every engine maps to LUTs and flip-flops; the DSP48E1 count is compared with the
    multiplier count (reported, not enforced, since DSP inference may differ between Yosys versions)."""
    ok = True
    for eng, L, kw, mult in SMOKE:
        r = synth.synth(f"lms_{eng}", synth.engine_files(eng), dict(L=L, **kw), tag=f"smoke_{eng}")
        note = "as expected" if r["DSP48E1"] == mult else f"expected {mult}"
        print(f"lms_{eng:9s} L={L}: DSP48E1 {r['DSP48E1']:3d} ({note}), LUT {r['LUT']}, FF {r['FF']}", flush=True)
        ok &= r["LUT"] > 0 and r["FF"] > 0
    if not ok:
        print("an engine mapped to no LUTs or flip-flops: the netlist or the stat parser is wrong")
    return 0 if ok else 1


def main():
    if not synth.have_yosys():
        print("yosys not found")
        return 2
    if "--smoke" in sys.argv:
        return smoke()
    rows = []
    out = REPO / "results" / "synth_engines.csv"
    for eng, L, kw in CONFIGS:
        t0 = time.time()
        params = dict(L=L, **kw)
        tag = f"{eng}_L{L}" + "".join(f"_{k}{v}" for k, v in kw.items())
        r = synth.synth(f"lms_{eng}", synth.engine_files(eng), params, tag=tag)
        row = dict(engine=eng, L=L, P=kw.get("P", ""), TDL=kw.get("TDL", 0), seconds=round(time.time() - t0, 1),
                   **{k: r[k] for k in FIELDS[4:-1]})
        rows.append(row)
        print(" ".join(f"{k}={row[k]}" for k in FIELDS), flush=True)
        with open(out, "w", newline="") as f:
            w = csv.DictWriter(f, FIELDS)
            w.writeheader()
            w.writerows(rows)
    print("wrote", out.relative_to(REPO))
    return 0


if __name__ == "__main__":
    sys.exit(main())
