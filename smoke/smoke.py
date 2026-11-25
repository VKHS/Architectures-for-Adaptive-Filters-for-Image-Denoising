"""Smoke tests: every scenario through its RTL top and its HLS C++ top, against the bit-accurate model.

    python smoke/smoke.py                      # scenarios A-F, RTL and HLS
    python smoke/smoke.py A D                  # some scenarios
    python smoke/smoke.py --only rtl           # one implementation (rtl or hls)
    python smoke/smoke.py --ap-types DIR       # HLS with the ap_int headers in DIR (a Vitis HLS include folder,
                                               # or the open HLS_arbitrary_Precision_Types/include)
    python smoke/smoke.py --vitis D            # compare the outputs of a Vitis HLS run (smoke/run_vitis.sh)
    python smoke/smoke.py --list D             # the case names only

A case is a small corrupted crop (a few hundred pixels) with its configuration. The golden output comes from
afarch (the same models the experiments use); the RTL runs in Icarus Verilog through the testbenches of tb/, the
HLS code is compiled with g++ as a C simulation (hls/tb). Both must reproduce the golden output word for word.
Every case also leaves build/smoke/<case>/vitis_case.tcl, its configuration for the Vitis HLS flow.
A full run writes results/smoke.json; every run prints one line per case.
"""
import json
import shutil
import sys
import time
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
from afarch import hdl, hwrun, scenarios as sc, frontends as fe, reference as ref                   # noqa: E402
from afarch.engines import Engine, ENGINE_CLASS, adaptation_delay, commit_delay                      # noqa: E402
from afarch.fxp import Arith                                                                         # noqa: E402

OUT = hdl.BUILD / "smoke"


def crop(name, h, w, i0=200, j0=200):
    return ref.load(name)[i0:i0 + h, j0:j0 + w]


def runner(fn, last=None, **kw):
    """A case's runner: (impl 'rtl' | 'hls' | 'vitis', ap_types) -> output words (the last `last` rows).
    The RTL testbenches insert random idle cycles between pixels (10 %): the tops must not care."""
    def run(impl, ap_types=None):
        out = fn(impl=impl, ap_types=ap_types, idle=10, **kw)
        return out if last is None else out[-last:]
    return run


# ------------------------------------------------------------------------------------------- scenarios
def case_a(engine, *, S=10, h=24, w=32, passes=2):
    ar = Arith(S=S)
    x = crop("coffee", h, w)
    freqs = [(0.031, 0.0), (0.012, 0.137)]
    i, j = np.mgrid[0:h, 0:w]
    y = x + 0.1 * np.cos(2 * np.pi * (freqs[0][0] * i + freqs[0][1] * j) + 0.4) \
          + 0.05 * np.cos(2 * np.pi * (freqs[1][0] * i + freqs[1][1] * j) + 1.3)
    codes = np.clip(ar.code(y), 0, None)
    off = int(ar.code((codes / 4096.0).mean()))
    golden = ar.code(sc.scenario_a(codes / 4096.0, freqs, S=S, engine=engine, passes=passes, offset=off)).ravel()
    name = f"A_{engine}"
    run = runner(hwrun.scen_a, last=h * w, work=OUT / name, codes=codes, freqs=freqs, S=S, engine=engine,
                 passes=passes, off=off)
    return dict(name=name, scenario="A", engine=engine, pixels=h * w, golden=golden, run=run,
                what=f"2 plane waves, L = 4, {passes} passes")


def case_b(mode, *, S=6, SK=0, tau=0.08, h=16, w=48, seed=0):
    from afarch.scenes import afm_scene
    ar = Arith(S=S)
    rng = np.random.default_rng(seed)
    x = afm_scene((64, 64), n_obj=6, seed=4)[24:24 + h, 8:8 + w]
    j = np.arange(w)[None, :]
    y = x + 0.05 * rng.standard_normal((h, 1)) + 0.1 * j / w + 0.01 * rng.standard_normal(x.shape)
    codes = np.clip(ar.code(y), 0, None)
    out, track = sc.scenario_b(codes / 4096.0, S=S, mode=mode, sk=SK, tau=tau)
    golden = np.stack([ar.code(out).ravel(), ar.code(track).ravel()], 1)
    name = f"B_{mode}"
    run = runner(hwrun.scen_b, work=OUT / name, codes=codes, S=S, mode=mode, SK=SK, TAU=int(round(tau * 4096)))
    return dict(name=name, scenario="B", engine="bias", pixels=h * w, golden=golden, run=run,
                what=f"{mode} update, S = {S}")


def case_c(engine, *, L=16, DELAY=6, S=6, h=6, w=64):
    ar = Arith(S=S)
    x = crop("chelsea", h, w)
    j = np.arange(w)[None, :]
    i = np.arange(h)[:, None]
    y = x - np.median(x) + 0.12 * np.cos(2 * np.pi * (0.1 * j + 0.03 * i) + 0.4)    # signed codes, about half < 0
    codes = ar.code(y)
    golden = ar.code(sc.scenario_c(codes / 4096.0, S=S, L=L, delay=DELAY, engine=engine)).ravel()
    name = f"C_{engine}"
    run = runner(hwrun.scen_c, work=OUT / name, codes=codes, S=S, L=L, DELAY=DELAY, engine=engine)
    return dict(name=name, scenario="C", engine=engine, pixels=h * w, golden=golden, run=run,
                what=f"L = {L}, delay {DELAY}")


def case_de(engine, *, R=2, HOLE=0, gated=False, S=7, passes=2, h=24, w=32, seed=0):
    ar = Arith(S=S)
    rng = np.random.default_rng(seed)
    if gated:
        x = crop("gravel", h, w)
        y = x.copy()
        hit = rng.random(x.shape) < 0.12
        y[hit] = rng.random(int(hit.sum()))
    else:
        x = crop("camera", h, w)
        y = x + 0.08 * rng.standard_normal(x.shape)
    codes = np.clip(ar.code(y), 0, None)
    yq = codes / 4096.0
    off = int(ar.code(np.median(yq) if gated else yq.mean()))
    L = len(fe.tap_offsets(R, HOLE))
    model = sc.scenario_de(yq, S=S, R=R, H=HOLE, engine=engine, passes=passes, gated=gated, offset=off / 4096.0)
    mo = model[0] if gated else model
    flags = (model[1].ravel() if gated else np.zeros(h * w, bool)).astype(np.int64)
    golden = np.stack([ar.code(mo).ravel(), flags], 1)
    scen = "D" if (R == 2 and HOLE == 0) else "E"
    name = f"{scen}_{'gated_' if gated else ''}{engine}"
    run = runner(hwrun.scen_de, last=h * w, work=OUT / name, codes=codes, R=R, HOLE=HOLE, S=S, engine=engine,
                 passes=passes, gated=gated, off=off)
    what = f"{2 * R + 1} x {2 * R + 1} window, blind spot {2 * HOLE + 1} x {2 * HOLE + 1}, L = {L}"
    return dict(name=name, scenario=scen, engine=engine, pixels=h * w, golden=golden, run=run,
                what=what + (", gated" if gated else "") + f", {passes} passes")


def f_golden(frames, *, S, xsel, engine, lognob=4):
    """What scen_f_top computes on a frame sequence (mode 0 frozen, 1 adapt on the scene, 2 adapt on the OB)."""
    ar = Arith(S=S)
    nob = 1 << lognob
    inv = ((1 << ar.FD) + (nob - 1) // 2) // (nob - 1)
    eng = Engine(ar, 1, ENGINE_CLASS[engine], D=adaptation_delay(engine, 1), Dc=commit_delay(engine, 1), out="e")
    out = []
    for mode, pix, obc, rf in frames:
        h, w = pix.shape
        for r in range(h):
            ssum = int(obc[r].sum())
            if mode == 2:
                xl = ((ssum - obc[r]) * inv) >> ar.FD
                eng.process(xl.reshape(-1, 1), obc[r], adapt=np.ones(nob, bool))
            X = (rf[r] if xsel else np.full(w, ssum >> lognob)).reshape(-1, 1)
            res = sc.run_row(eng, engine, X, pix[r], adapt=np.full(w, mode == 1), drain=sc.default_drain(engine, 1))
            out += list(res["out"])
        eng.finish()
    return np.array(out, np.int64)


def case_f(variant, *, engine="serial", S=1, h=10, w=40, seed=0):
    ar = Arith(S=S)
    rng = np.random.default_rng(seed)
    NOB = 16
    x = crop("hubble", h, w, 100, 100)

    def frame():
        return 0.03 * rng.standard_normal(h), 0.03 * np.sign(rng.standard_normal((h, w)))

    c, t = frame()
    scene = x + c[:, None] + t + 0.01 * rng.standard_normal((h, w))
    ob = c[:, None] + 0.01 * rng.standard_normal((h, NOB))
    refc = 0.8 * t + 0.01 * rng.standard_normal((h, w))
    cd, td = frame()
    dark = cd[:, None] + td + 0.01 * rng.standard_normal((h, w))
    dark_ob = cd[:, None] + 0.01 * rng.standard_normal((h, NOB))
    dark_ref = 0.8 * td + 0.01 * rng.standard_normal((h, w))
    q = ar.code
    xsel = 1 if variant == "channel" else 0
    if variant == "online":
        frames = [(2, q(scene), q(ob), q(refc))]
    elif variant == "channel":
        frames = [(1, q(dark), q(dark_ob), q(dark_ref)), (0, q(scene), q(ob), q(refc))]
    else:
        frames = [(1, q(dark), q(dark_ob), q(dark_ref))] * 2 + [(0, q(scene), q(ob), q(refc))]
    golden = f_golden(frames, S=S, xsel=xsel, engine=engine)
    name = f"F_{variant}"
    run = runner(hwrun.scen_f, work=OUT / name, frames=frames, S=S, xsel=xsel, engine=engine)
    what = {"ob_cal": "OB reference, 2 dark frames then a frozen frame", "online": "OB reference, online (mode 2)",
            "channel": "reference channel, dark frame then frozen"}[variant] + f", S = {S}"
    return dict(name=name, scenario="F", engine=engine, pixels=len(golden), golden=golden, run=run, what=what)


CASES = {
    "A": lambda: [case_a("serial"), case_a("df")],
    "B": lambda: [case_b("lms"), case_b("sign", S=6, SK=2), case_b("gated", S=4)],
    "C": lambda: [case_c("folded"), case_c("df"), case_c("rowblock")],
    "D": lambda: [case_de("serial", gated=True, passes=3), case_de("df", gated=True, passes=3), case_de("systolic")],
    "E": lambda: [case_de("systolic", R=3, HOLE=1), case_de("rowblock", R=3, HOLE=1), case_de("da", R=3, HOLE=0)],
    "F": lambda: [case_f("ob_cal"), case_f("online", S=-3), case_f("channel", S=-1)],
}


def compare(got, golden):
    """Word-for-word comparison; a word is one output sample (all of its columns)."""
    got, golden = np.asarray(got, np.int64), np.asarray(golden, np.int64)
    if got.size != golden.size:
        return False, f"{got.size} outputs for {golden.size}"
    diff = (got.reshape(golden.shape) != golden).reshape(len(golden), -1).any(axis=1)
    bad = np.nonzero(diff)[0]
    return len(bad) == 0, ("" if len(bad) == 0 else f"{len(bad)} words differ, first at {bad[0]}")


def main(argv):
    only, ap, vitis, sel = None, None, False, []
    it = iter(argv)
    for a in it:
        if a == "--only":
            only = next(it)
        elif a == "--ap-types":
            ap = next(it)
        elif a == "--vitis":
            vitis, only = True, "hls"
        elif a == "--list":
            only = "list"
        else:
            sel.append(a.upper())
    sel = sel or list(CASES)
    unknown = [s for s in sel if s not in CASES]
    if unknown:
        print(f"unknown scenario {unknown}: choose from {list(CASES)}")
        return 2
    if only == "list":                                  # the case names, for smoke/run_vitis.sh
        for s in sel:
            for c in CASES[s]():
                print(c["name"])
        return 0
    do_rtl = only in (None, "rtl")
    do_hls = only in (None, "hls")
    if do_rtl and not hdl.have_iverilog():
        print("iverilog not found: skipping the RTL (use --only hls)")
        do_rtl = False
    if do_hls and not vitis and not shutil.which("g++"):
        print("g++ not found: skipping the HLS C simulation")
        do_hls = False
    hls_impl = "vitis" if vitis else "hls"
    print(f"{'case':22s} {'pixels':>6s}  {'RTL':6s} {'Vitis' if vitis else 'HLS':6s}  configuration")
    results, allok = [], True
    t0 = time.time()
    for s in sel:
        for c in CASES[s]():
            row = dict(case=c["name"], scenario=c["scenario"], engine=c["engine"], pixels=c["pixels"], what=c["what"])
            for col, impl, on in (("rtl", "rtl", do_rtl), ("hls", hls_impl, do_hls)):
                if not on:
                    row[col] = "skip"
                    continue
                ok, note = compare(c["run"](impl, ap), c["golden"])
                row[col] = "PASS" if ok else "FAIL"
                if note:
                    row[col + "_note"] = note
                allok &= ok
            print(f"{c['name']:22s} {c['pixels']:6d}  {row['rtl']:6s} {row['hls']:6s}  {c['what']}", flush=True)
            results.append(row)
    print(f"{'ALL PASS' if allok else 'FAILURES'} ({time.time() - t0:.0f} s)")
    if do_rtl and do_hls and not vitis and sel == list(CASES):
        (REPO / "results" / "smoke.json").write_text(json.dumps(dict(cases=results, all_pass=allok,
                                                                     ap_types=bool(ap)), indent=1))
    return 0 if allok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
