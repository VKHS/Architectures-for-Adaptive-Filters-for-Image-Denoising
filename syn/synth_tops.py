"""Yosys synth_xilinx (xc7) cell counts of the scenario tops at 512 x 512 (front end + engine).

    python syn/synth_tops.py             # writes results/synth_tops.csv
    python syn/synth_tops.py A D         # re-runs only these scenarios and keeps the other rows of the csv
"""
import csv
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from afarch import synth                                                  # noqa: E402
from afarch.hdl import REPO, RTL                                          # noqa: E402

ENG = {"serial": 0, "folded": 1, "df": 2, "systolic": 3, "rowblock": 4, "da": 5}
COMMON = [RTL / "common" / "lms_err_unit.v", RTL / "common" / "adder_tree.v"] + \
         sorted((RTL / "engines").glob("lms_*.v"))
COS = str(RTL / "scenarios" / "cos1024_q12.hex")
# two harmonics with non-zero increments (constant phases would let synthesis fold the ROM away)
_U = [int(round(0.0185 * 2 ** 32)), int(round(0.137 * 2 ** 32))]
_V = [int(round(0.0925 * 2 ** 32)), int(round(0.061 * 2 ** 32))]
UINC = _U[0] | (_U[1] << 32)
VINC = _V[0] | (_V[1] << 32)
CONFIGS = [
    ("A", "scen_a_top", "serial", dict(W=512, HH=512, K=2, ENGINE=0, UINC=UINC, VINC=VINC)),
    ("A", "scen_a_top", "df", dict(W=512, HH=512, K=2, ENGINE=2, UINC=UINC, VINC=VINC)),
    ("B", "scen_b_top", "bias", dict(W=512, MODE=2)),
    ("C", "scen_c_top", "folded P=8", dict(W=512, HH=512, L=128, DELAY=8, ENGINE=1, P=8)),
    ("C", "scen_c_top", "systolic", dict(W=512, HH=512, L=128, DELAY=8, ENGINE=3)),
    ("D", "scen_de_top", "serial", dict(W=512, HH=512, R=2, HOLE=0, ENGINE=0)),
    ("D", "scen_de_top", "folded P=6", dict(W=512, HH=512, R=2, HOLE=0, ENGINE=1, P=6)),
    ("D", "scen_de_top", "df", dict(W=512, HH=512, R=2, HOLE=0, ENGINE=2)),
    ("D gated", "scen_de_top", "df", dict(W=512, HH=512, R=2, HOLE=0, ENGINE=2, GATED=1)),
    ("E", "scen_de_top", "systolic", dict(W=512, HH=512, R=3, HOLE=0, ENGINE=3)),
    ("F", "scen_f_top", "serial", dict(W=512, ENGINE=0)),
    ("baseline", "median3x3_top", "median", dict(W=512, HH=512, SWITCH=1)),
]
FIELDS = ["scenario", "top", "engine", "DSP48E1", "LUT", "FF", "SRL", "LUTRAM", "RAMB18", "RAMB36", "CARRY4", "MUXF",
          "seconds"]


def main():
    only = set(sys.argv[1:])
    out = REPO / "results" / "synth_tops.csv"
    old = {}
    if only and out.exists():
        with open(out) as f:
            old = {(r["scenario"], r["engine"]): r for r in csv.DictReader(f)}
    rows = [old.get((scn, eng)) for scn, _, eng, _ in CONFIGS]     # kept rows of a partial run
    for i, (scn, top, eng, params) in enumerate(CONFIGS):
        if only and scn.split()[0] not in only:
            continue
        t0 = time.time()
        p = {k: v for k, v in params.items() if v is not None}
        files = COMMON + [RTL / "scenarios" / f"{top}.v"]
        if top in ("scen_de_top", "median3x3_top"):
            files.append(RTL / "scenarios" / "window_gen.v")
        if top == "median3x3_top":
            files = [RTL / "scenarios" / "window_gen.v", RTL / "baselines" / "median3x3_top.v"]
        tag = f"top_{scn}_{eng}".replace(" ", "_").replace("=", "")
        extra = [f"chparam -set COS_FILE \"{COS}\" {top}"] if top == "scen_a_top" else []
        r = synth.synth(top, files, p, tag=tag, extra=extra)
        rows[i] = dict(scenario=scn, top=top, engine=eng, seconds=round(time.time() - t0, 1),
                       **{k: r[k] for k in FIELDS[3:-1]})
        print(" ".join(f"{k}={rows[i][k]}" for k in FIELDS), flush=True)
        with open(out, "w", newline="") as f:
            w = csv.DictWriter(f, FIELDS)
            w.writeheader()
            w.writerows(r for r in rows if r)
    print("wrote", out.relative_to(REPO))


if __name__ == "__main__":
    main()
