"""Bit-exact regression of the six engines (rtl/engines) against the models (afarch/engines.py).

    python sim/test_engines.py            # all cases
    python sim/test_engines.py df da      # only some engines

Every case drives tb/tb_engine.v with a step file that mixes samples, idle cycles (no advance), pre-roll shifts
(tapped-delay-line mode) and drain bursts of random length, then compares every output word (o, y, e, flag)
with the model. Handshake engines also get a back-to-back run that measures the initiation interval.
Writes results/rtl_engine_tests.json.
"""
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from afarch import hdl                                                    # noqa: E402
from afarch.engines import Gate, run, adaptation_delay, commit_delay    # noqa: E402
from afarch.fxp import Arith                                             # noqa: E402

REPO = hdl.REPO
TB = REPO / "tb" / "tb_engine.v"
ENGINE_ID = {"serial": 0, "folded": 1, "df": 2, "systolic": 3, "rowblock": 4, "da": 5}
PIPELINED = ("df", "systolic", "rowblock")
RULE_ID = {"lms": 0, "se": 1, "sd": 2, "ss": 3}
OUT_ID = {"e": 0, "y": 1, "p-y": 2, "gated": 3}


def clog2(v):
    return int(np.ceil(np.log2(v))) if v > 1 else 0


def expected_ii(engine, L, P, adapt=True, WD=16):
    if engine == "serial":
        return 2 * L + 3 if adapt else L + 3
    if engine == "folded":
        return -(-L // P) + clog2(P) + 5
    if engine == "da":
        return WD + clog2(-(-L // 4)) + 3
    return 1


def build_steps(engine, L, rng, n, TDL, gated, last_rows):
    """Random step stream. Returns a list of dict steps (valid samples carry data later)."""
    D = adaptation_delay(engine, L) if engine in ("df", "systolic") else 0
    Dc = commit_delay(engine, L)
    steps = []
    k = 0
    while k < n:
        if TDL:
            for _ in range(int(rng.integers(0, L + 4))):          # pre-roll shifts
                steps.append(dict(v=0, s=1, dr=0))
        row = int(rng.integers(4, 30))
        for j in range(row):
            if k >= n:
                break
            if engine in PIPELINED and rng.random() < 0.15:
                steps.append(dict(v=0, s=0, dr=0))                   # idle, no advance
            if engine not in PIPELINED and rng.random() < 0.1:
                steps.append(dict(v=0, s=0, dr=0))
            steps.append(dict(v=1, s=0, dr=0, last=int(last_rows and (j == row - 1 or k == n - 1))))
            k += 1
        if engine in PIPELINED:
            m = int(rng.integers(0, max(D, Dc) + 5))
            if engine == "rowblock" and rng.random() < 0.7:
                m = max(m, Dc + 1)
            for _ in range(m):
                steps.append(dict(v=0, s=0, dr=1))
    if engine in PIPELINED:
        for _ in range(max(D, Dc) + L + 8):
            steps.append(dict(v=0, s=0, dr=1))
    return steps


def fill(steps, L, rng, ar, TDL, gated, wtrue):
    """Give every step its data; build the model's tap matrix from the step stream (TDL: from the x0 chain)."""
    WD = ar.WD
    q = 1 << ar.FD
    chain = np.zeros(L, np.int64)
    u = 0.0
    for st in steps:
        st.setdefault("last", 0)
        if TDL:
            u = 0.85 * u + 0.5 * rng.standard_normal()
            x0 = int(np.clip(round(u * 0.4 * q), -(1 << (WD - 1)), (1 << (WD - 1)) - 1))
            advance = st["v"] or st["s"] or st["dr"]
            if st["dr"]:
                x0 = 0
            if advance:
                chain = np.concatenate([[x0], chain[:-1]])
            st["x"] = chain.copy() if advance else chain.copy()
            st["xin"] = np.array([x0] + [0] * (L - 1))
        else:
            x = np.round(rng.standard_normal(L) * 0.35 * q).astype(np.int64)
            if rng.random() < 0.02:
                x[rng.integers(0, L)] = rng.choice([-(1 << (WD - 1)), (1 << (WD - 1)) - 1])
            st["x"] = x
            st["xin"] = x
        if st["v"]:
            xr = st["x"] / q
            d = float(wtrue @ xr) + 0.05 * rng.standard_normal()
            if gated and rng.random() < 0.08:
                d += rng.choice([-1, 1]) * rng.uniform(0.6, 1.5)
            if rng.random() < 0.01:
                d = rng.choice([-7.99, 7.99])
            st["d"] = int(ar.code(d))
            st["p"] = int(ar.code(d + 0.25 * rng.standard_normal()))
            st["a"] = int(rng.random() < 0.9)
        else:
            st["d"] = st["p"] = 0
            st["a"] = 0


def model_outputs(engine, ar, steps, L, out, gated, A0):
    cls = {"serial": "lms", "folded": "lms", "da": "block", "df": "dlms", "systolic": "dlms",
           "rowblock": "block"}[engine]
    if engine in PIPELINED:
        st = [s for s in steps if s["v"] or s["s"] or s["dr"]]
    else:
        st = [s for s in steps if s["v"]]
    X = np.array([s["x"] for s in st], np.int64).reshape(len(st), L)
    kw = dict(adapt=[s["a"] for s in st], p=[s["p"] for s in st], valid=[bool(s["v"]) for s in st],
              last=[bool(s["last"]) for s in st], engine=cls, out=out,
              D=adaptation_delay(engine, L), Dc=commit_delay(engine, L),
              A=np.full(L, A0, np.int64), gate=Gate(ar) if gated else None)
    r = run(ar, X, [s["d"] for s in st], **kw)
    return np.stack([r["out"], r["y"], r["e"], r["flag"].astype(np.int64)], 1)


def run_case(name, engine, L, *, P=2, TDL=0, rule="lms", leak=0, out="e", gated=False, w0=0.0, S=6, n=260,
             seed=1):
    rng = np.random.default_rng(seed)
    ar = Arith(S=S, rule=rule, leak=leak)
    A0 = int(ar.acc_from_weight(w0)) if w0 else 0
    wtrue = rng.uniform(-0.6, 0.6, L) / np.sqrt(L)
    steps = build_steps(engine, L, rng, n, TDL, gated, last_rows=engine in ("rowblock", "da"))
    fill(steps, L, rng, ar, TDL, gated, wtrue)
    stim = hdl.BUILD / f"{name}.stim"
    log = hdl.BUILD / f"{name}.log"
    hdl.BUILD.mkdir(exist_ok=True)
    hdl.write_steps(stim, [(s["v"], s["s"], s["dr"], s["a"], s["last"], s["d"], s["p"], s["xin"])
                           for s in steps], ar.WD)
    params = dict(ENGINE=ENGINE_ID[engine], L=L, P=P, TDL=TDL, S=S, RULE=RULE_ID[rule], LEAK=leak,
                  OUT=OUT_ID[out], GATED=int(gated), A0=A0, STIM=str(stim), LOG=str(log), TAIL=8 * L + 200)
    hdl.simulate("tb_engine", TB, params, tag=name)
    acc, outs = hdl.read_log(log)
    exp = model_outputs(engine, ar, steps, L, out, gated, A0)
    got = outs[:, 1:]
    ok = got.shape == exp.shape and np.array_equal(got, exp)
    bad = None
    if not ok:
        nmin = min(len(got), len(exp))
        diff = np.nonzero(np.any(got[:nmin] != exp[:nmin], axis=1))[0]
        bad = dict(n_rtl=len(got), n_model=len(exp), first=int(diff[0]) if len(diff) else None,
                   rtl=got[diff[0]].tolist() if len(diff) else None, model=exp[diff[0]].tolist() if len(diff) else None)
    res = dict(case=name, engine=engine, L=L, P=P if engine == "folded" else None, TDL=TDL, rule=rule, leak=leak,
               out=out, gated=gated, samples=int(len(exp)), flagged=int(exp[:, 3].sum()), match=bool(ok))
    if bad:
        res["mismatch"] = bad
    return res


def run_ii(name, engine, L, P=2, S=6, seed=2):
    """Back-to-back samples (no idle lines) to measure the initiation interval of a handshake engine."""
    rng = np.random.default_rng(seed)
    ar = Arith(S=S)
    n = 24
    steps = [dict(v=1, s=0, dr=0, last=0) for _ in range(n)]
    fill(steps, L, rng, ar, 0, False, rng.uniform(-0.3, 0.3, L) / np.sqrt(L))
    for s in steps:
        s["a"] = 1
    stim = hdl.BUILD / f"{name}.stim"
    log = hdl.BUILD / f"{name}.log"
    hdl.write_steps(stim, [(s["v"], s["s"], s["dr"], s["a"], s["last"], s["d"], s["p"], s["xin"])
                           for s in steps], ar.WD)
    params = dict(ENGINE=ENGINE_ID[engine], L=L, P=P, S=S, STIM=str(stim), LOG=str(log), TAIL=8 * L + 200)
    hdl.simulate("tb_engine", TB, params, tag=name)
    acc, outs = hdl.read_log(log)
    ii = np.diff(acc)
    return dict(case=name, engine=engine, L=L, P=P if engine == "folded" else None,
                ii_measured=int(np.median(ii)), ii_formula=expected_ii(engine, L, P),
                latency_first_output=int(outs[0, 0] - acc[0]) if len(outs) else None)


CASES = [
    ("serial_L4", "serial", 4, {}),
    ("serial_L5_se", "serial", 5, dict(rule="se", S=10)),
    ("serial_L3_gated", "serial", 3, dict(out="gated", gated=True, w0=1 / 3)),
    ("serial_L6_leak_py", "serial", 6, dict(leak=9, out="p-y")),
    ("folded_L8_P2", "folded", 8, dict(P=2)),
    ("folded_L7_P3_sd", "folded", 7, dict(P=3, rule="sd", S=9)),
    ("folded_L5_P1", "folded", 5, dict(P=1)),
    ("folded_L8_P8_gated", "folded", 8, dict(P=8, out="gated", gated=True, w0=1 / 8)),
    ("df_L8", "df", 8, {}),
    ("df_L5_sd_y", "df", 5, dict(rule="sd", S=9, out="y")),
    ("df_L16_tdl", "df", 16, dict(TDL=1, S=7)),
    ("df_L1", "df", 1, {}),
    ("df_L6_gated", "df", 6, dict(out="gated", gated=True, w0=1 / 6)),
    ("systolic_L4", "systolic", 4, {}),
    ("systolic_L6_tdl_ss", "systolic", 6, dict(TDL=1, rule="ss", S=14)),
    ("systolic_L1", "systolic", 1, {}),
    ("systolic_L5_gated_leak", "systolic", 5, dict(out="gated", gated=True, w0=0.2, leak=10)),
    ("rowblock_L8", "rowblock", 8, dict(S=8)),
    ("rowblock_L6_tdl_leak", "rowblock", 6, dict(TDL=1, leak=8, S=8)),
    ("rowblock_L3_py", "rowblock", 3, dict(out="p-y", S=8)),
    ("da_L8", "da", 8, dict(S=8)),
    ("da_L6_se", "da", 6, dict(rule="se", S=12)),
    ("da_L13_gated", "da", 13, dict(out="gated", gated=True, w0=1 / 13, S=8)),
    ("da_L4_leak", "da", 4, dict(leak=7, S=8)),
]
II_CASES = [("ii_serial_L8", "serial", 8, 1), ("ii_serial_L24", "serial", 24, 1),
            ("ii_folded_L24_P1", "folded", 24, 1), ("ii_folded_L24_P4", "folded", 24, 4),
            ("ii_folded_L24_P6", "folded", 24, 6), ("ii_folded_L48_P12", "folded", 48, 12),
            ("ii_da_L24", "da", 24, 1), ("ii_da_L128", "da", 128, 1)]


def main(selected):
    if not hdl.have_iverilog():
        print("iverilog/vvp not found: install Icarus Verilog")
        sys.exit(2)
    results, iis = [], []
    for name, eng, L, kw in CASES:
        if selected and eng not in selected:
            continue
        r = run_case(name, eng, L, **kw)
        results.append(r)
        print(f"{'PASS' if r['match'] else 'FAIL'}  {name:26s} {r['samples']:4d} samples, {r['flagged']:3d} flagged"
              + ("" if r["match"] else f"   {r['mismatch']}"), flush=True)
    for name, eng, L, P in II_CASES:
        if selected and eng not in selected:
            continue
        r = run_ii(name, eng, L, P)
        iis.append(r)
        print(f"{'PASS' if r['ii_measured'] == r['ii_formula'] else 'FAIL'}  {name:26s} II {r['ii_measured']} "
              f"(formula {r['ii_formula']}), first output after {r['latency_first_output']} cycles", flush=True)
    allok = all(r["match"] for r in results) and all(r["ii_measured"] == r["ii_formula"] for r in iis)
    if not selected:
        out = REPO / "results" / "rtl_engine_tests.json"
        out.parent.mkdir(exist_ok=True)
        out.write_text(json.dumps(dict(cases=results, initiation_intervals=iis, all_pass=allok), indent=1))
        print("wrote", out.relative_to(REPO))
    print("ALL PASS" if allok else "FAILURES")
    return 0 if allok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
