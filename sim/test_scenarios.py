"""Bit-exact regression of the scenario tops (rtl/scenarios) against afarch.scenarios.

    python sim/test_scenarios.py            # all
    python sim/test_scenarios.py de c       # some

Each case streams a small corrupted image through the RTL top (with random idle cycles) and compares every
output pixel with the fixed-point pipeline of the same scenario. Writes results/rtl_scenario_tests.json.
"""
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from afarch import hdl, scenarios as sc, frontends as fe, reference as ref                  # noqa: E402
from afarch.engines import adaptation_delay, commit_delay                                  # noqa: E402
from afarch.fxp import Arith                                                                # noqa: E402

REPO = hdl.REPO
ENGINE_ID = {"serial": 0, "folded": 1, "df": 2, "systolic": 3, "rowblock": 4, "da": 5}
SCEN_DIRS = ("common", "engines", "scenarios")


def write_hex(path, codes):
    with open(path, "w") as f:
        for c in np.asarray(codes).ravel():
            f.write(f"{int(c) & 0xFFFF:04x}\n")


def read_log(path):
    rows = [ln.split()[1:] for ln in Path(path).read_text().splitlines() if ln.startswith("O ")]
    return np.array(rows, dtype=np.int64).reshape(-1, 2) if rows else np.zeros((0, 2), np.int64)


def crop(name, h, w, i0=200, j0=200):
    return ref.load(name)[i0:i0 + h, j0:j0 + w]


# ------------------------------------------------------------------------------------------- D / E
def case_de(name, engine, *, R=2, HOLE=0, gated=False, S=7, passes=2, P=2, h=24, w=32, seed=0):
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
    OFF = int(ar.code(np.median(yq) if gated else yq.mean()))
    L = len(fe.tap_offsets(R, HOLE))
    A0 = int(ar.acc_from_weight(1.0 / L)) if gated else 0
    drain_row = sc.default_drain(engine, L)
    model = sc.scenario_de(yq, S=S, R=R, H=HOLE, engine=engine, passes=passes, gated=gated, offset=OFF / 4096.0)
    mo = model[0] if gated else model
    exp_pix = ar.code(mo).ravel()
    exp_flag = (model[1].ravel() if gated else np.zeros(h * w, bool)).astype(np.int64)
    img = hdl.BUILD / f"{name}.hex"
    log = hdl.BUILD / f"{name}.log"
    hdl.BUILD.mkdir(exist_ok=True)
    write_hex(img, codes)
    params = dict(W=w, HH=h, R=R, HOLE=HOLE, ENGINE=ENGINE_ID[engine], P=P, S=S, GATED=int(gated), A0=A0,
                  DRAIN_ROW=drain_row, DRAIN_FRAME=L + 16, PASSES=passes, OFF=OFF, IMG=str(img), LOG=str(log))
    hdl.simulate("tb_scen_de", REPO / "tb" / "tb_scen_de.v", params, rtl_dirs=SCEN_DIRS, tag=name)
    got = read_log(log)
    n = h * w
    last = got[-n:] if len(got) >= n else got
    ok = len(got) == passes * n and np.array_equal(last[:, 0], exp_pix) and np.array_equal(last[:, 1], exp_flag)
    res = dict(case=name, scenario="E" if (R > 2 or HOLE > 0) else ("D gated" if gated else "D"), engine=engine,
               R=R, HOLE=HOLE, L=L, passes=passes, pixels=n, outputs=int(len(got)), match=bool(ok),
               flagged=int(exp_flag.sum()))
    if not ok and len(last) == n:
        bad = np.nonzero((last[:, 0] != exp_pix) | (last[:, 1] != exp_flag))[0]
        res["first_mismatch"] = dict(index=int(bad[0]), rtl=last[bad[0]].tolist(),
                                     model=[int(exp_pix[bad[0]]), int(exp_flag[bad[0]])], count=int(len(bad)))
    return res


# ------------------------------------------------------------------------------------------------ C
def case_c(name, engine, *, L=16, DELAY=6, S=6, P=2, h=6, w=64, seed=0):
    ar = Arith(S=S)
    x = crop("chelsea", h, w)
    j = np.arange(w)[None, :]
    i = np.arange(h)[:, None]
    y = x + 0.12 * np.cos(2 * np.pi * (0.1 * j + 0.03 * i) + 0.4)
    codes = np.clip(ar.code(y), 0, None)
    yq = codes / 4096.0
    drain_row = sc.default_drain(engine, L)
    exp_pix = ar.code(sc.scenario_c(yq, S=S, L=L, delay=DELAY, engine=engine)).ravel()
    img = hdl.BUILD / f"{name}.hex"
    log = hdl.BUILD / f"{name}.log"
    hdl.BUILD.mkdir(exist_ok=True)
    write_hex(img, codes)
    params = dict(W=w, HH=h, L=L, DELAY=DELAY, ENGINE=ENGINE_ID[engine], P=P, S=S, DRAIN_ROW=drain_row,
                  DRAIN_FRAME=2 * L + 16, IMG=str(img), LOG=str(log))
    hdl.simulate("tb_scen_c", REPO / "tb" / "tb_scen_c.v", params, rtl_dirs=SCEN_DIRS, tag=name)
    got = read_log(log)
    n = h * w
    ok = len(got) == n and np.array_equal(got[:, 0], exp_pix)
    res = dict(case=name, scenario="C", engine=engine, L=L, delay=DELAY, pixels=n, outputs=int(len(got)),
               match=bool(ok))
    if not ok and len(got) == n:
        bad = np.nonzero(got[:, 0] != exp_pix)[0]
        res["first_mismatch"] = dict(index=int(bad[0]), rtl=int(got[bad[0], 0]), model=int(exp_pix[bad[0]]),
                                     count=int(len(bad)))
    return res


# ------------------------------------------------------------------------------------------------ A
def case_a(name, engine, *, S=10, P=2, h=24, w=32, passes=2, seed=0):
    ar = Arith(S=S)
    x = crop("coffee", h, w)
    freqs = [(0.031, 0.0), (0.012, 0.137)]
    i, j = np.mgrid[0:h, 0:w]
    y = x + 0.1 * np.cos(2 * np.pi * (freqs[0][0] * i + freqs[0][1] * j) + 0.4) \
          + 0.05 * np.cos(2 * np.pi * (freqs[1][0] * i + freqs[1][1] * j) + 1.3)
    codes = np.clip(ar.code(y), 0, None)
    yq = codes / 4096.0
    OFF = int(ar.code(yq.mean()))
    L = 2 * len(freqs)
    exp_pix = ar.code(sc.scenario_a(yq, freqs, S=S, engine=engine, passes=passes, offset=OFF)).ravel()
    U, V = fe.phase_increments(freqs)
    pack = lambda vs: sum(int(v) << (32 * k) for k, v in enumerate(vs))  # noqa: E731
    img = hdl.BUILD / f"{name}.hex"
    log = hdl.BUILD / f"{name}.log"
    hdl.BUILD.mkdir(exist_ok=True)
    write_hex(img, codes)
    params = dict(W=w, HH=h, K=len(freqs), ENGINE=ENGINE_ID[engine], P=P, S=S, UINC=pack(U), VINC=pack(V),
                  DRAIN_ROW=sc.default_drain(engine, L), DRAIN_FRAME=L + 16, PASSES=passes, OFF=OFF,
                  IMG=str(img), LOG=str(log), COS_FILE=str(REPO / "rtl" / "scenarios" / "cos1024_q12.hex"))
    hdl.simulate("tb_scen_a", REPO / "tb" / "tb_scen_a.v", params, rtl_dirs=SCEN_DIRS, tag=name)
    got = read_log(log)
    n = h * w
    last = got[-n:]
    ok = len(got) == passes * n and np.array_equal(last[:, 0], exp_pix)
    res = dict(case=name, scenario="A", engine=engine, L=L, passes=passes, pixels=n, outputs=int(len(got)),
               match=bool(ok))
    if not ok and len(last) == n:
        bad = np.nonzero(last[:, 0] != exp_pix)[0]
        res["first_mismatch"] = dict(index=int(bad[0]), rtl=int(last[bad[0], 0]), model=int(exp_pix[bad[0]]),
                                     count=int(len(bad)))
    return res


# ------------------------------------------------------------------------------------------------ B
def write_bf(path, lines):
    with open(path, "w") as f:
        for m, fl, px, rf in lines:
            f.write(f"{int(m)} {int(fl)} {int(px)} {int(rf)}\n")


def case_b(name, engine, *, mode="lms", S=6, SK=0, tau=0.08, h=16, w=48, seed=0):
    from afarch.scenes import afm_scene
    ar = Arith(S=S)
    rng = np.random.default_rng(seed)
    x = afm_scene((64, 64), n_obj=6, seed=4)[24:24 + h, 8:8 + w]
    j = np.arange(w)[None, :]
    y = x + 0.05 * rng.standard_normal((h, 1)) + 0.1 * j / w + 0.01 * rng.standard_normal(x.shape)
    codes = np.clip(ar.code(y), 0, None)
    yq = codes / 4096.0
    out, track = sc.scenario_b(yq, S=S, mode=mode, sk=SK, tau=tau)
    exp = np.stack([ar.code(out).ravel(), ar.code(track).ravel()], 1)
    stim = hdl.BUILD / f"{name}.stim"
    log = hdl.BUILD / f"{name}.log"
    hdl.BUILD.mkdir(exist_ok=True)
    write_bf(stim, [(0, 0, c, 0) for c in codes.ravel()])
    params = dict(TOP=0, W=w, S=S, MODE={"lms": 0, "sign": 1, "gated": 2}[mode], SK=SK,
                  TAU=int(round(tau * 4096)), STIM=str(stim), LOG=str(log))
    hdl.simulate("tb_scen_bf", REPO / "tb" / "tb_scen_bf.v", params, rtl_dirs=SCEN_DIRS, tag=name)
    got = read_log(log)
    ok = got.shape == exp.shape and np.array_equal(got, exp)
    res = dict(case=name, scenario="B", engine="bias", mode=mode, pixels=h * w, outputs=int(len(got)),
               match=bool(ok))
    if not ok and got.shape == exp.shape:
        bad = np.nonzero(np.any(got != exp, 1))[0]
        res["first_mismatch"] = dict(index=int(bad[0]), rtl=got[bad[0]].tolist(), model=exp[bad[0]].tolist())
    return res


# ------------------------------------------------------------------------------------------------ F
def case_f(name, engine, *, variant="ob_cal", S=1, h=10, w=40, seed=0):
    from afarch.engines import Engine, ENGINE_CLASS
    ar = Arith(S=S)
    rng = np.random.default_rng(seed)
    NOB = 16
    x = crop("hubble", h, w, 100, 100)

    def frame():
        c = 0.03 * rng.standard_normal(h)
        t = 0.03 * np.sign(rng.standard_normal((h, w)))
        return c, t

    c, t = frame()
    scene = x + c[:, None] + t + 0.01 * rng.standard_normal((h, w))
    ob = c[:, None] + 0.01 * rng.standard_normal((h, NOB))
    refc = 0.8 * t + 0.01 * rng.standard_normal((h, w))
    cd, td = frame()
    dark = cd[:, None] + td + 0.01 * rng.standard_normal((h, w))
    dark_ob = cd[:, None] + 0.01 * rng.standard_normal((h, NOB))
    dark_ref = 0.8 * td + 0.01 * rng.standard_normal((h, w))
    q = lambda a: ar.code(a)  # noqa: E731
    xsel = 1 if variant == "channel" else 0
    if variant == "online":
        frames = [(2, q(scene), q(ob), q(refc))]
    elif variant == "channel":
        frames = [(1, q(dark), q(dark_ob), q(dark_ref)), (0, q(scene), q(ob), q(refc))]
    else:
        frames = [(1, q(dark), q(dark_ob), q(dark_ref))] * 2 + [(0, q(scene), q(ob), q(refc))]
    L = 1
    eng = Engine(ar, 1, ENGINE_CLASS[engine], D=adaptation_delay(engine, L), Dc=commit_delay(engine, L), out="e")
    drain_row = sc.default_drain(engine, L)
    lines, exp = [], []
    INV = (4096 + (NOB - 1) // 2) // (NOB - 1)
    for mode, pix, obc, ref in frames:
        for r in range(h):
            for k in range(NOB):
                lines.append((mode, 0, obc[r, k], 0))
            ssum = int(obc[r].sum())
            xob = ssum >> 4
            if mode == 2:
                xl = ((ssum - obc[r]) * INV) >> 12
                eng.process(xl.reshape(-1, 1), obc[r], adapt=np.ones(NOB, bool))
            X = (ref[r] if xsel else np.full(w, xob)).reshape(-1, 1)
            res = sc.run_row(eng, engine, X, pix[r], adapt=np.full(w, mode == 1), drain=drain_row)
            exp += list(res["out"])
            for j in range(w):
                lines.append((mode, 0, pix[r, j], ref[r, j]))
        eng.finish()
        lines.append((mode, 1, 0, 0))
    stim = hdl.BUILD / f"{name}.stim"
    log = hdl.BUILD / f"{name}.log"
    write_bf(stim, lines)
    params = dict(TOP=1, W=w, S=S, NOB=NOB, LOGNOB=4, XSEL=xsel, ENGINE=ENGINE_ID[engine], DRAIN_ROW=drain_row,
                  STIM=str(stim), LOG=str(log))
    hdl.simulate("tb_scen_bf", REPO / "tb" / "tb_scen_bf.v", params, rtl_dirs=SCEN_DIRS, tag=name)
    got = read_log(log)[:, 0]
    exp = np.array(exp, np.int64)
    ok = got.shape == exp.shape and np.array_equal(got, exp)
    res = dict(case=name, scenario="F", engine=engine, variant=variant, pixels=int(len(exp)), outputs=int(len(got)),
               match=bool(ok))
    if not ok and got.shape == exp.shape:
        bad = np.nonzero(got != exp)[0]
        res["first_mismatch"] = dict(index=int(bad[0]), rtl=int(got[bad[0]]), model=int(exp[bad[0]]))
    return res


# ------------------------------------------------------------------------------------------ baselines
def case_median(name, engine, *, switch=0, thr=0.1, h=24, w=32, seed=0):
    from scipy.ndimage import median_filter
    ar = Arith()
    rng = np.random.default_rng(seed)
    x = crop("gravel", h, w)
    y = x.copy()
    hit = rng.random(x.shape) < 0.1
    y[hit] = rng.random(int(hit.sum()))
    codes = np.clip(ar.code(y), 0, None)
    med = median_filter(codes, size=3, mode="mirror")
    T = int(round(thr * 4096))
    if switch:
        out = np.where(np.abs(codes - med) > T, med, codes)
    else:
        out = med
    img = hdl.BUILD / f"{name}.hex"
    log = hdl.BUILD / f"{name}.log"
    hdl.BUILD.mkdir(exist_ok=True)
    write_hex(img, codes)
    params = dict(W=w, HH=h, SWITCH=switch, THR=T, IMG=str(img), LOG=str(log))
    hdl.simulate("tb_median", REPO / "tb" / "tb_median.v", params,
                 rtl_dirs=("common", "scenarios", "baselines"), tag=name)
    got = read_log(log)[:, 0]
    exp = out.ravel()
    ok = got.shape == exp.shape and np.array_equal(got, exp)
    return dict(case=name, scenario="baseline", engine="median3x3" + ("-switching" if switch else ""),
                pixels=h * w, outputs=int(len(got)), match=bool(ok))


CASES = {
    "de": [
        ("de_D_serial", "serial", {}),
        ("de_D_folded", "folded", dict(P=4)),
        ("de_D_df", "df", {}),
        ("de_D_systolic", "systolic", {}),
        ("de_D_rowblock", "rowblock", dict(S=10)),
        ("de_D_da", "da", dict(S=10)),
        ("de_Dg_serial", "serial", dict(gated=True, S=6, passes=3)),
        ("de_Dg_df", "df", dict(gated=True, S=6, passes=3)),
        ("de_E_folded_hole1", "folded", dict(R=3, HOLE=1, P=8, S=9)),
        ("de_E_systolic_hole1", "systolic", dict(R=3, HOLE=1, S=9)),
    ],
}
CASES["c"] = [
    ("c_serial", "serial", {}),
    ("c_folded", "folded", dict(P=4)),
    ("c_df", "df", {}),
    ("c_systolic", "systolic", {}),
    ("c_rowblock", "rowblock", dict(S=9)),
    ("c_da", "da", dict(S=9)),
]
CASES["a"] = [
    ("a_serial", "serial", {}),
    ("a_folded", "folded", dict(P=1)),
    ("a_df", "df", {}),
    ("a_systolic", "systolic", {}),
    ("a_rowblock", "rowblock", dict(S=13)),
    ("a_da", "da", dict(S=13)),
]
CASES["b"] = [
    ("b_lms", "bias", dict(mode="lms", S=6)),
    ("b_sign", "bias", dict(mode="sign", S=4, SK=2)),
    ("b_gated", "bias", dict(mode="gated", S=4)),
]
CASES["f"] = [
    ("f_ob_cal_serial", "serial", dict(variant="ob_cal")),
    ("f_ob_cal_df", "df", dict(variant="ob_cal")),
    ("f_online_serial", "serial", dict(variant="online", S=2)),
    ("f_online_rowblock", "rowblock", dict(variant="online", S=2)),
    ("f_channel_systolic", "systolic", dict(variant="channel", S=-1)),
]
CASES["median"] = [
    ("median3x3", "median", dict(switch=0)),
    ("switching_median", "median", dict(switch=1)),
]
RUNNERS = {"de": case_de, "c": case_c, "a": case_a, "b": case_b, "f": case_f, "median": case_median}


def main(selected):
    if not hdl.have_iverilog():
        print("iverilog/vvp not found")
        return 2
    results = []
    for group, cases in CASES.items():
        if selected and group not in selected:
            continue
        for name, engine, kw in cases:
            r = RUNNERS[group](name, engine, **kw)
            results.append(r)
            print(f"{'PASS' if r['match'] else 'FAIL'}  {name:24s} {r['pixels']} px x {r.get('passes', 1)} "
                  f"passes, {r['outputs']} outputs" + ("" if r["match"] else f"   {r.get('first_mismatch')}"),
                  flush=True)
    allok = all(r["match"] for r in results)
    if not selected:
        out = REPO / "results" / "rtl_scenario_tests.json"
        out.write_text(json.dumps(dict(cases=results, all_pass=allok), indent=1))
        print("wrote", out.relative_to(REPO))
    print("ALL PASS" if allok else "FAILURES")
    return 0 if allok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
