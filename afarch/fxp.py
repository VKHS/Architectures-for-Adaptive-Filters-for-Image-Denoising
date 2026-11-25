"""Fixed-point arithmetic shared by every engine: the bit-level contract between the models and the RTL.

Signals and their formats (defaults):

    pixel data x, d, y, e, p   signed WD = 16 bits, FD = 12 fractional bits   (Q12, range [-8, 8))
    weight view w               signed WW = 24 bits, FW = 20 fractional bits   (Q20, range [-8, 8))
    accumulators                signed WA = 48 bits (two's complement), as in a DSP48E1 P register

An adaptive weight is *stored* as an exact accumulator A of update products and *used* through a view:

    g     = e * x                                  update product, FD + FD = 24 fractional bits
    A    <- A + g                                  exact, never rounded
    w     = sat_WW(A >>> V),  V = 2 FD - FW + S    the step mu = 2^-S is a choice of bit slice

so the step size costs no hardware, an update never "stalls" below the weight LSB, and the update adder is the
accumulator of the DSP slice that computes g. The filter output is rounded once:

    y = sat_WD((RND + sum_k w_k x_k) >>> FW),  RND = 2^(FW-1)   (round half up; RND preloads the accumulator)
    e = sat_WD(d - y)

Every function here works on Python ints and on numpy int64 arrays, and matches rtl/common/lms_arith.vh.
"""
from dataclasses import dataclass, replace

import numpy as np

RULES = ("lms", "se", "sd", "ss")       # LMS, sign-error, sign-data, sign-sign


def smin(bits):
    return -(1 << (bits - 1))


def smax(bits):
    return (1 << (bits - 1)) - 1


def sat(v, bits):
    """Signed saturation to ``bits`` (two's complement)."""
    if isinstance(v, np.ndarray):
        return np.clip(v, smin(bits), smax(bits))
    return max(smin(bits), min(smax(bits), int(v)))


def wrap(v, bits):
    """Two's complement wrap-around to ``bits`` (what a register of that width does)."""
    m = (1 << bits) - 1
    h = 1 << (bits - 1)
    if isinstance(v, np.ndarray):
        return ((v + h) & m) - h
    return ((int(v) + h) & m) - h


def sgn(v):
    if isinstance(v, np.ndarray):
        return np.sign(v).astype(np.int64)
    return (v > 0) - (v < 0)


@dataclass(frozen=True)
class Arith:
    """Word lengths, step and update rule of one adaptive filter.

    S     : step exponent, mu = 2^-S (for rule "se" the error is replaced by +-1.0, so mu multiplies sgn(e))
    rule  : "lms" (e x), "se" (sgn(e) x), "sd" (e sgn(x)) or "ss" (sgn(e) sgn(x))
    leak  : 0 for none, else A <- A - (A >>> leak) + g on every applied update (leaky LMS)
    qupdate: model a classic weight REGISTER of FW fractional bits instead of the accumulator: every update is
             rounded to the weight LSB before it is added, so updates smaller than half an LSB are lost
             ("stalling"); used only by experiments/wordlength.py
    """
    WD: int = 16
    FD: int = 12
    WW: int = 24
    FW: int = 20
    WA: int = 48
    S: int = 7
    rule: str = "lms"
    leak: int = 0
    qupdate: bool = False

    def __post_init__(self):
        assert self.rule in RULES, self.rule
        assert self.V >= 1, "the view shift 2FD - FW + S must be at least 1"
        assert self.WW <= self.WA - self.V

    def with_(self, **kw):
        return replace(self, **kw)

    # ---------------------------------------------------------------------------------------- formats
    @property
    def V(self):
        """Right shift from the accumulator A (2FD fractional bits, scaled by mu) to the weight view (FW)."""
        return 2 * self.FD - self.FW + self.S

    @property
    def RND(self):
        return 1 << (self.FW - 1)

    @property
    def mu(self):
        return 2.0 ** -self.S

    def code(self, v):
        """Float (array) -> Q(FD) codes, rounded to nearest and saturated."""
        return sat(np.round(np.asarray(v, float) * (1 << self.FD)).astype(np.int64), self.WD)

    def real(self, c):
        return np.asarray(c, float) / (1 << self.FD)

    def acc_from_weight(self, w):
        """Accumulator value whose view is the weight w (float or array, in real units)."""
        wq = np.round(np.asarray(w, float) * (1 << self.FW)).astype(np.int64)
        return wq << self.V

    def weight_real(self, A):
        return self.view(A).astype(float) / (1 << self.FW)

    # ------------------------------------------------------------------------------------- operations
    def view(self, A):
        return sat(A >> self.V, self.WW)

    def filt(self, A, x):
        """Filter output y for accumulators A and taps x (1-D int64 arrays)."""
        acc = self.RND + int(np.dot(self.view(A), x))
        assert -(1 << (self.WA - 1)) <= acc < (1 << (self.WA - 1)), "filter accumulator overflow"
        return sat(acc >> self.FW, self.WD)

    def error(self, d, y):
        return sat(int(d) - int(y), self.WD)

    def grad(self, e, x):
        """Update product g (int64 array, units of 2^-2FD) for error e and taps x."""
        x = np.asarray(x, np.int64)
        if self.rule == "lms":
            return int(e) * x
        if self.rule == "se":
            return sgn(int(e)) * (x << self.FD)
        if self.rule == "sd":
            return (int(e) << self.FD) * sgn(x)
        return (sgn(int(e)) << (2 * self.FD)) * sgn(x)

    def apply(self, A, g):
        """One applied update (in place on the int64 accumulator array)."""
        if self.leak:
            A -= A >> self.leak
        if self.qupdate:
            g = ((g + (1 << (self.V - 1))) >> self.V) << self.V
        A += g
        assert np.all(np.abs(A) < (1 << (self.WA - 1))), "weight accumulator overflow"
        return A


def step_exponent(alpha, n_taps, var):
    """Power-of-two step closest (in log) to the normalised software step mu2 = alpha / (n_taps var)."""
    mu = alpha / (n_taps * var)
    return int(round(-np.log2(mu)))
