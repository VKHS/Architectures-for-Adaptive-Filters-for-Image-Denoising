"""Yosys synthesis for Xilinx 7-series (synth_xilinx -family xc7): cell counts of a module.

These are Yosys's technology-mapped counts, not Vivado's post-implementation utilisation; they show how each
architecture scales, which resource it consumes and whether the multipliers land in DSP48E1 slices.
"""
import re
import shutil
import subprocess

from .hdl import RTL, BUILD

GROUPS = {
    "DSP48E1": ["DSP48E1"],
    "LUT": ["LUT1", "LUT2", "LUT3", "LUT4", "LUT5", "LUT6"],
    "FF": ["FDRE", "FDSE", "FDCE", "FDPE"],
    "SRL": ["SRL16E", "SRLC32E"],
    "LUTRAM": ["RAM16X1D", "RAM32X1D", "RAM64X1D", "RAM128X1D", "RAM256X1D", "RAM32M", "RAM64M", "RAM16X1S",
               "RAM32X1S", "RAM64X1S", "RAM128X1S", "RAM32M16", "RAM64M8"],
    "RAMB18": ["RAMB18E1"],
    "RAMB36": ["RAMB36E1"],
    "CARRY4": ["CARRY4"],
    "MUXF": ["MUXF7", "MUXF8"],
}


def have_yosys():
    return shutil.which("yosys") is not None


def synth(top, files, params=None, tag=None, timeout=3600, flatten=True, extra=()):
    """Synthesize ``top`` from ``files`` with parameter overrides. Returns a dict of grouped cell counts."""
    params = params or {}
    tag = tag or top
    d = BUILD / "syn"
    d.mkdir(parents=True, exist_ok=True)
    stat = d / f"{tag}.stat"
    lines = [f"read_verilog -I {RTL / 'common'} " + " ".join(str(f) for f in files)]
    for k, v in params.items():
        v = int(v)
        lit = f"{max(64, v.bit_length())}'d{v}" if v >= 2 ** 31 else str(v)
        lines.append(f"chparam -set {k} {lit} {top}")
    lines += list(extra)
    lines.append(f"synth_xilinx -family xc7 -top {top} -noiopad -noclkbuf" + (" -flatten" if flatten else ""))
    lines.append(f"tee -q -o {stat} stat")
    script = d / f"{tag}.ys"
    script.write_text("\n".join(lines) + "\n")
    # run from rtl/scenarios: ROM tables ($readmemh) resolve there during the default elaboration of read_verilog
    r = subprocess.run(["yosys", "-q", "-s", str(script)], capture_output=True, text=True, timeout=timeout,
                       cwd=RTL / "scenarios")
    if r.returncode != 0:
        raise RuntimeError(f"yosys failed for {tag}:\n{r.stderr[-3000:]}")
    return parse_stat(stat.read_text())


def parse_stat(text):
    """Cell counts from Yosys `stat`: '  12   LUT2' (recent versions) or '  LUT2   12' (0.3x and older)."""
    cells = {}
    for m in re.finditer(r"^\s+(\d+)\s+([A-Za-z_$][\w$]*)\s*$", text, re.M):
        cells[m.group(2)] = cells.get(m.group(2), 0) + int(m.group(1))
    for m in re.finditer(r"^\s+([A-Za-z_$][\w$]*)\s+(\d+)\s*$", text, re.M):
        cells[m.group(1)] = cells.get(m.group(1), 0) + int(m.group(2))
    out = {g: sum(cells.get(c, 0) for c in names) for g, names in GROUPS.items()}
    out["cells"] = cells
    return out


def engine_files(engine):
    common = [RTL / "common" / "lms_err_unit.v", RTL / "common" / "adder_tree.v"]
    return common + [RTL / "engines" / f"lms_{engine}.v"]
