"""Scenario inputs through the RTL tops (Icarus Verilog) and the HLS tops (g++ C simulation of hls/).

Every function takes the same Q12 codes as the models of afarch.scenarios and returns the raw output words of the
chosen implementation, so a caller can compare them with the model word for word: smoke/smoke.py does that on
small cases, experiments/examples_hw.py on the full application examples.

    impl = "rtl"     the Verilog top in its testbench (tb/), Icarus Verilog
    impl = "hls"     the C++ top in its testbench (hls/tb/), compiled with g++; ap_types = a folder with ap_int.h
                     selects the exact-width ap_int types, otherwise 64-bit integers
    impl = "vitis"   read the output a Vitis HLS run left behind (hls/scripts/run_vitis_hls.tcl)

Every HLS run also writes vitis_case.tcl into its work folder: the configuration of the same run for Vitis HLS.
"""
import subprocess
from pathlib import Path

import numpy as np

from . import hdl, frontends as fe
from .fxp import Arith
from .scenarios import default_drain

REPO = hdl.REPO
HLS = REPO / "hls"
ENGINE_ID = {"serial": 0, "folded": 1, "df": 2, "systolic": 3, "rowblock": 4, "da": 5}
SCEN_DIRS = ("common", "engines", "scenarios")
COS_FILE = REPO / "rtl" / "scenarios" / "cos1024_q12.hex"


# ----------------------------------------------------------------------------------------------- files
def write_hex(path, codes):
    with open(path, "w") as f:
        for c in np.asarray(codes).ravel():
            f.write(f"{int(c) & 0xFFFF:04x}\n")


def write_txt(path, codes):
    np.savetxt(path, np.asarray(codes, np.int64).ravel(), fmt="%d")


def write_bf(path, lines):
    """Step file of tb/tb_scen_bf.v: one line per pixel, mode flush pix ref."""
    with open(path, "w") as f:
        for m, fl, px, rf in lines:
            f.write(f"{int(m)} {int(fl)} {int(px)} {int(rf)}\n")


def read_log(path):
    rows = [ln.split()[1:] for ln in Path(path).read_text().splitlines() if ln.startswith("O ")]
    return np.array(rows, dtype=np.int64).reshape(-1, 2) if rows else np.zeros((0, 2), np.int64)


# --------------------------------------------------------------------------------------------- runners
def rtl_run(work, tb, params):
    work = Path(work)
    work.mkdir(parents=True, exist_ok=True)
    log = work / "rtl_log.txt"
    hdl.simulate(tb, REPO / "tb" / f"{tb}.v", dict(params, LOG=str(log)), rtl_dirs=SCEN_DIRS,
                 tag=f"{work.name}_{tb}", timeout=24 * 3600)
    return read_log(log)


def write_vitis_case(work, top, tb, flags, args):
    """The run's configuration for hls/scripts/run_vitis_hls.tcl: top, sources, defines, testbench arguments."""
    argv = [str(args[0]), str(work / "vitis_out.txt")] + [str(a) for a in args[1:]]
    (work / "vitis_case.tcl").write_text(
        f"# Written by afarch/hwrun.py: {work.name}, for hls/scripts/run_vitis_hls.tcl\n"
        f"set af_top    {{{top}_top}}\n"
        f"set af_src    {{{HLS / 'src' / (top + '.cpp')}}}\n"
        f"set af_tb     {{{HLS / 'tb' / (tb + '.cpp')}}}\n"
        f"set af_cflags {{-DAFHLS_AP_TYPES -I{HLS / 'include'} {' '.join(flags)}}}\n"
        f"set af_argv   {{{' '.join(argv)}}}\n")


def hls_run(work, tb, defines, args, ap_types=None, vitis=False):
    """Compile hls/tb/<tb>.cpp with its top for this configuration and run it (or read a Vitis HLS output)."""
    work = Path(work)
    work.mkdir(parents=True, exist_ok=True)
    top = tb.replace("tb_", "")
    flags = [f"-D{k}={v}" for k, v in defines.items()]
    write_vitis_case(work, top, tb, flags, args)
    if vitis:
        out = work / "vitis_out.txt"
        if not out.exists():
            raise RuntimeError(f"{out} not found: run hls/scripts/run_vitis_hls.tcl for {work.name} first")
        return np.loadtxt(out, dtype=np.int64, ndmin=2)
    exe = work / f"{tb}.bin"
    cmd = ["g++", "-std=c++14", "-O2", "-Wall", "-Wno-unknown-pragmas", "-Wno-unused-label",
           f"-I{HLS / 'include'}", f"-I{HLS / 'csim'}"]
    if ap_types:
        cmd += ["-DAFHLS_AP_TYPES", "-isystem", str(ap_types)]      # warnings inside the ap_int headers are theirs
    cmd += flags + [str(HLS / "tb" / f"{tb}.cpp"), str(HLS / "src" / f"{top}.cpp"), "-o", str(exe)]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        errs = [ln for ln in r.stderr.splitlines() if "error" in ln]
        raise RuntimeError("g++ failed:\n" + "\n".join(errs[:20] or r.stderr.splitlines()[-30:]))
    out = work / "hls_out.txt"
    r = subprocess.run([str(exe), str(args[0]), str(out)] + [str(a) for a in args[1:]], capture_output=True,
                       text=True, timeout=24 * 3600)
    if r.returncode != 0:
        raise RuntimeError(f"{tb} failed:\n{r.stderr[-2000:]}")
    return np.loadtxt(out, dtype=np.int64, ndmin=2)


def _hls(impl, ap_types):
    assert impl in ("hls", "vitis", "rtl"), impl
    return dict(ap_types=ap_types, vitis=impl == "vitis")


# ------------------------------------------------------------------------------------------- scenarios
def scen_a(work, codes, freqs, *, S, engine, passes, off, impl, P=2, ap_types=None, idle=0):
    """A: the notch on plane-wave references. Returns the output codes of every pass (passes * H * W)."""
    work = Path(work)
    work.mkdir(parents=True, exist_ok=True)
    h, w = codes.shape
    K = len(freqs)
    L = 2 * K
    U, V = fe.phase_increments(freqs)
    if impl == "rtl":
        pack = lambda vs: sum(int(v) << (32 * k) for k, v in enumerate(vs))  # noqa: E731
        write_hex(work / "img.hex", codes)
        params = dict(W=w, HH=h, K=K, ENGINE=ENGINE_ID[engine], P=P, S=S, UINC=pack(U), VINC=pack(V),
                      DRAIN_ROW=default_drain(engine, L), DRAIN_FRAME=L + 16, PASSES=passes, OFF=off,
                      IMG=str(work / "img.hex"), COS_FILE=str(COS_FILE), IDLE_PROB=idle)
        return rtl_run(work, "tb_scen_a", params)[:, 0]
    write_txt(work / "img.txt", codes)
    return hls_run(work, "tb_scen_a", dict(A_W=w, A_H=h, A_K=K, A_S=S, ENGINE=ENGINE_ID[engine], ENG_P=P),
                   [work / "img.txt", off, passes] + U + V, **_hls(impl, ap_types))[:, 0]


def scen_b(work, codes, *, S, mode, SK=0, TAU=0, impl, ap_types=None, idle=0):
    """B: the bias canceller. Returns (H * W, 2): output e and bias b."""
    work = Path(work)
    work.mkdir(parents=True, exist_ok=True)
    h, w = codes.shape
    mid = {"lms": 0, "sign": 1, "gated": 2}[mode]
    if impl == "rtl":
        write_bf(work / "stim.txt", [(0, 0, c, 0) for c in np.asarray(codes).ravel()])
        params = dict(TOP=0, W=w, S=S, MODE=mid, SK=SK, TAU=TAU, STIM=str(work / "stim.txt"), IDLE_PROB=idle)
        return rtl_run(work, "tb_scen_bf", params)
    write_txt(work / "img.txt", codes)
    return hls_run(work, "tb_scen_b", dict(B_W=w, B_H=h, B_S=S, B_MODE=mid, B_SK=SK, B_TAU=TAU),
                   [work / "img.txt"], **_hls(impl, ap_types))


def scen_c(work, codes, *, S, L, DELAY, engine, impl, P=2, ap_types=None, idle=0):
    """C: the canceller without a reference. Returns the output codes (H * W)."""
    work = Path(work)
    work.mkdir(parents=True, exist_ok=True)
    h, w = codes.shape
    if impl == "rtl":
        write_hex(work / "img.hex", codes)
        params = dict(W=w, HH=h, L=L, DELAY=DELAY, ENGINE=ENGINE_ID[engine], P=P, S=S,
                      DRAIN_ROW=default_drain(engine, L), DRAIN_FRAME=2 * L + 16, IMG=str(work / "img.hex"),
                      IDLE_PROB=idle)
        return rtl_run(work, "tb_scen_c", params)[:, 0]
    write_txt(work / "img.txt", codes)
    return hls_run(work, "tb_scen_c", dict(C_W=w, C_H=h, C_L=L, C_DELAY=DELAY, C_S=S, ENGINE=ENGINE_ID[engine],
                                           ENG_P=P), [work / "img.txt"], **_hls(impl, ap_types))[:, 0]


def scen_de(work, codes, *, R, HOLE, S, engine, passes, gated, off, impl, P=2, ap_types=None, idle=0):
    """D / E: the blind-spot predictor. Returns (passes * H * W, 2): output pixel and gate flag, every pass."""
    work = Path(work)
    work.mkdir(parents=True, exist_ok=True)
    h, w = codes.shape
    L = len(fe.tap_offsets(R, HOLE))
    if impl == "rtl":
        write_hex(work / "img.hex", codes)
        A0 = int(Arith(S=S).acc_from_weight(1.0 / L)) if gated else 0
        params = dict(W=w, HH=h, R=R, HOLE=HOLE, ENGINE=ENGINE_ID[engine], P=P, S=S, GATED=int(gated), A0=A0,
                      DRAIN_ROW=default_drain(engine, L), DRAIN_FRAME=L + 16, PASSES=passes, OFF=off,
                      IMG=str(work / "img.hex"), IDLE_PROB=idle)
        return rtl_run(work, "tb_scen_de", params)
    write_txt(work / "img.txt", codes)
    a0_wq = int(np.round((1 << 20) / L)) if gated else 0
    return hls_run(work, "tb_scen_de", dict(DE_W=w, DE_H=h, DE_R=R, DE_HOLE=HOLE, DE_S=S, DE_GATED=int(gated),
                                            ENGINE=ENGINE_ID[engine], ENG_P=P),
                   [work / "img.txt", off, a0_wq, passes], **_hls(impl, ap_types))


def scen_f(work, frames, *, S, xsel, engine="serial", lognob=4, impl, ap_types=None, idle=0):
    """F: the reference-sensor canceller over a sequence of frames (mode, pix, ob, ref), all codes, with
    mode 0 frozen, 1 adapt on the scene (dark frame), 2 adapt on the OB pixels (online). Returns the output
    codes of every frame (frames * H * W)."""
    work = Path(work)
    work.mkdir(parents=True, exist_ok=True)
    nob = 1 << lognob
    h, w = frames[0][1].shape
    if impl == "rtl":
        lines = []
        for mode, pix, ob, rf in frames:
            for r in range(h):
                lines += [(mode, 0, ob[r, k], 0) for k in range(nob)]
                lines += [(mode, 0, pix[r, j], rf[r, j] if rf is not None else 0) for j in range(w)]
            lines.append((mode, 1, 0, 0))
        write_bf(work / "stim.txt", lines)
        params = dict(TOP=1, W=w, S=S, NOB=nob, LOGNOB=lognob, XSEL=xsel, ENGINE=ENGINE_ID[engine],
                      DRAIN_ROW=default_drain(engine, 1), STIM=str(work / "stim.txt"), IDLE_PROB=idle)
        return rtl_run(work, "tb_scen_bf", params)[:, 0]
    flat = [len(frames)]
    for mode, pix, ob, rf in frames:
        flat.append(mode)
        for r in range(h):
            flat += [int(v) for v in ob[r]] + [int(v) for v in pix[r]] + ([int(v) for v in rf[r]] if xsel else [])
    write_txt(work / "frames.txt", flat)
    return hls_run(work, "tb_scen_f", dict(F_W=w, F_H=h, F_LOGNOB=lognob, F_XSEL=xsel, F_S=S,
                                           ENGINE=ENGINE_ID[engine]), [work / "frames.txt"],
                   **_hls(impl, ap_types))[:, 0]
