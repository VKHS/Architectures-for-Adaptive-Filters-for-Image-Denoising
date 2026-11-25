"""Analytic time and area models of the six engines (formulas checked against the RTL; see docs/03-engines.md).

All counts are per engine instance for L taps, data width WD and accumulator width WA. II is the initiation
interval in clock cycles per sample (with adaptation), D the adaptation delay in samples, latency the clock
cycles from accepting a sample to its output. The DSP column is the number of multipliers, which Yosys maps
one-to-one onto DSP48E1 slices for these word lengths (24 x 16 and 16 x 16 products).
"""
import math

ENGINES = ("serial", "folded", "df", "systolic", "rowblock", "da")
LABEL = {"serial": "serial (1 MAC)", "folded": "folded (P lanes)", "df": "direct-form DLMS",
         "systolic": "systolic DLMS", "rowblock": "row-block LMS", "da": "distributed arithmetic"}
CLASS = {"serial": "exact LMS", "folded": "exact LMS", "df": "delayed LMS", "systolic": "delayed LMS",
         "rowblock": "block LMS", "da": "block LMS"}

RATES = {                                            # samples per second
    "512x512 @ 30 fps": 512 * 512 * 30,
    "1024x1024 @ 30 fps": 1024 * 1024 * 30,
    "1920x1080 @ 60 fps": 1920 * 1080 * 60,
}


def clog2(n):
    return int(math.ceil(math.log2(n))) if n > 1 else 0


def model(engine, L, P=1, WD=16, WA=48, WW=24, tdl=False):
    """Time and area of one engine. Returns a dict."""
    T = clog2(L)
    if engine == "serial":
        r = dict(mult=1, II=2 * L + 3, II_noadapt=L + 3, D=0, latency=L + 3,
                 state_bits=L * WA + L * WD)
    elif engine == "folded":
        M = -(-L // P)
        r = dict(mult=2 * P, II=M + clog2(P) + 5, II_noadapt=M + clog2(P) + 5, D=0, latency=M + clog2(P) + 5,
                 state_bits=L * WA + 2 * L * WD)
    elif engine == "df":
        xs = (L + T + 1) * WD if tdl else (T + 2) * L * WD
        r = dict(mult=2 * L, II=1, II_noadapt=1, D=T + 3, latency=T + 2, state_bits=L * WA + xs)
    elif engine == "systolic":
        xs = (3 * L + 1) * WD if tdl else sum(j + L + 2 for j in range(L)) * WD
        r = dict(mult=2 * L, II=1, II_noadapt=1, D=L + 3, latency=L + 2, state_bits=L * WA + xs + L * WD)
    elif engine == "rowblock":
        xs = (L + T + 1) * WD if tdl else (T + 2) * L * WD
        r = dict(mult=2 * L, II=1, II_noadapt=1, D=None, latency=T + 2, state_bits=2 * L * WA + xs,
                 row_drain=T + 4)
    elif engine == "da":
        NG = -(-L // 4)
        Tg = clog2(NG)
        r = dict(mult=0, II=WD + Tg + 3, II_noadapt=WD + Tg + 3, D=None, latency=WD + Tg + 3,
                 state_bits=2 * L * WA + 2 * L * WD + L * (2 * WD + 1) + NG * 16 * (WW + 2),
                 row_overhead=WD + 18)
    else:
        raise ValueError(engine)
    r.update(engine=engine, L=L, P=P if engine == "folded" else None, cls=CLASS[engine])
    return r


def iteration_bound(L, D=0, t_mul=1.0, t_add=0.25):
    """Iteration bound of the LMS loop in units of a multiplier delay.

    The loop w -> (x) -> adder tree -> (-) -> (x mu e) -> (x) -> (+) -> w contains two multiplications, a tree of
    ceil(log2 L) additions, the error subtraction and the update addition, and D + 1 registers.
    """
    return (2 * t_mul + (clog2(L) + 2) * t_add) / (D + 1)


def clock_for(rate, II):
    """Clock (Hz) an engine with initiation interval II needs for a sample rate."""
    return rate * II


def folded_lanes_for(L, rate, f_clk):
    """Smallest lane count P of lms_folded that reaches ``rate`` at ``f_clk`` (None if no P can)."""
    for P in range(1, L + 1):
        if model("folded", L, P)["II"] * rate <= f_clk:
            return P
    return None


def dlms_mu_bound(D):
    """Exact mean-stability bound of DLMS on one eigenmode: 0 < mu lambda < 2 sin(pi / (2 (2D + 1)))."""
    return 2.0 * math.sin(math.pi / (2.0 * (2 * D + 1)))


def worst_row_lambda(rows):
    """Largest lambda_max of the per-row tap correlation R_row = X^T X / N over an iterable of row tap matrices X
    (N x L). The row is the block of lms_rowblock and lms_da, so this is the lambda of their stability condition."""
    import numpy as np
    return max(float(np.linalg.eigvalsh(X.T @ X / len(X)).max()) for X in rows)


def block_step(lam_row, N, margin=1.0):
    """Smallest step exponent S (mu = 2^-S) with mu N lambda_row <= margin. The block-LMS condition is
    mu N lambda_max < 2; margin = 1 keeps a factor of two from it."""
    return int(math.ceil(math.log2(N * lam_row / margin)))
