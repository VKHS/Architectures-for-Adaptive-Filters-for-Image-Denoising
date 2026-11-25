"""Running the RTL from Python: Icarus Verilog compile/run helpers and step files for tb/tb_engine.v."""
import os
import shutil
import subprocess
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
RTL = REPO / "rtl"
BUILD = REPO / "build"


def have_iverilog():
    return shutil.which("iverilog") is not None and shutil.which("vvp") is not None


def sources(*subdirs):
    out = []
    for sd in subdirs:
        out += sorted(str(p) for p in (RTL / sd).glob("*.v"))
    return out


def vparam(v):
    if isinstance(v, str):
        return f'"{v}"'
    if isinstance(v, (bool, np.bool_)):
        return str(int(v))
    v = int(v)
    if v < 0:
        assert v >= -2 ** 31, "negative parameters must fit 32 bits"
        return str(v)
    if v >= 2 ** 31:
        return f"{max(64, v.bit_length())}'d{v}"
    return str(v)


def simulate(top, tb_file, params, rtl_dirs=("common", "engines"), extra=(), tag="sim", timeout=3600):
    """Compile ``tb_file`` with the RTL of ``rtl_dirs`` and run it. A compile warning is an error.
    Returns (vvp stdout, list of warnings), the list being empty."""
    BUILD.mkdir(exist_ok=True)
    out = BUILD / f"{tag}.vvp"
    cmd = ["iverilog", "-g2005", "-Wall", "-Wno-timescale", "-Wno-implicit-dimensions", "-I", str(RTL / "common"),
           "-s", top, "-o", str(out)]
    for k, v in params.items():
        cmd.append(f"-P{top}.{k}={vparam(v)}")
    cmd += sources(*rtl_dirs) + [str(p) for p in extra] + [str(tb_file)]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0 or "error" in r.stderr.lower():
        raise RuntimeError("iverilog failed:\n" + r.stderr + r.stdout)
    warn = [ln for ln in r.stderr.splitlines() if "warning" in ln.lower()]
    if warn:                                   # the RTL must compile without warnings under -Wall
        raise RuntimeError("iverilog warnings:\n" + "\n".join(warn))
    r = subprocess.run(["vvp", "-n", str(out)], capture_output=True, text=True, timeout=timeout)
    if r.returncode != 0:
        raise RuntimeError("vvp failed:\n" + r.stderr + r.stdout)
    return r.stdout, warn


def hexword(vec, WD):
    """Pack a tap vector (tap 0 in the least significant bits) as a hex string."""
    v = 0
    m = (1 << WD) - 1
    for k, t in enumerate(vec):
        v |= (int(t) & m) << (k * WD)
    return f"{v:x}"


def write_steps(path, steps, WD):
    """steps: iterable of (valid, shift, drain, adapt, last, d, p, xvec)."""
    with open(path, "w") as f:
        for (v, s, dr, a, l, d, p, x) in steps:
            f.write(f"{int(v)} {int(s)} {int(dr)} {int(a)} {int(l)} {int(d)} {int(p)} {hexword(x, WD)}\n")


def read_log(path):
    acc, outs = [], []
    for ln in Path(path).read_text().splitlines():
        t = ln.split()
        if not t:
            continue
        if t[0] == "I":
            acc.append(int(t[1]))
        elif t[0] == "O":
            outs.append(tuple(int(v) for v in t[1:]))
    return np.array(acc), np.array(outs, dtype=np.int64).reshape(-1, 5)


def env_with_tools():
    env = dict(os.environ)
    return env
