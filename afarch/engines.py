"""Bit-accurate models of the adaptive engines (what the RTL computes, sample by sample).

The six engine architectures fall into three algorithmic classes. Within a class the architectures differ only in
time and area, never in the numbers they produce, because two's complement accumulation is exact and its order
does not matter:

    exact LMS        lms_serial, lms_folded (any number of lanes P)     y(n) uses every update up to n-1
    delayed LMS      lms_df (D = tree depth + 3), lms_systolic (D = L + 3)
                     y(n) uses the updates up to n-1-D
    block LMS        lms_rowblock, lms_da                               weights frozen inside a block (a row),
                                                                        one summed update at the block's end

``run`` reproduces all three. The error unit (error, optional robust gate, output selection) is shared by all
engines and is modelled by ``ErrUnit``.
"""
from collections import deque
from dataclasses import dataclass

import numpy as np

from .fxp import Arith, sat

OUT_MODES = ("e", "y", "p-y", "gated")


class Gate:
    """Robust error gate of the gated self-tuning filter (rtl/common/lms_err_unit.v).

    A sample is flagged when |e| > max(|s| << KS, TMIN), s being a running scale of the clean errors:
        s <- s + (1.5 |e| - s) >> RATE        (only on samples that are not flagged)
    s carries FRAC extra fractional bits. Defaults follow the software: k = 4, a rate of 1/128 (~0.01),
    1.5 ~ 1.4826 (the MAD-to-sigma factor), a floor t_min = 0.1 and a start value of 0.05.
    """

    def __init__(self, ar: Arith, ks=2, rate=7, t_min=0.1, s0=0.05, frac=8):
        self.ks, self.rate, self.frac = ks, rate, frac
        self.tmin = int(ar.code(t_min))
        self.s0 = int(ar.code(s0)) << frac
        self.s = self.s0

    def reset(self):
        self.s = self.s0

    def threshold(self):
        return max((self.s >> self.frac) << self.ks, self.tmin)

    def __call__(self, e):
        ae = abs(int(e))
        flag = ae > self.threshold()
        if not flag:
            target = (ae + (ae >> 1)) << self.frac
            self.s += (target - self.s) >> self.rate
        return flag


@dataclass
class ErrUnit:
    """e = sat(d - y); optional gate; output select: e | y | p - y | gated (flag ? y : p)."""
    ar: Arith
    out: str = "e"
    gate: Gate = None

    def __post_init__(self):
        assert self.out in OUT_MODES
        assert (self.out == "gated") == (self.gate is not None)

    def __call__(self, y, d, p):
        e = self.ar.error(d, y)
        flag = self.gate(e) if self.gate is not None else False
        if self.out == "e":
            o = e
        elif self.out == "y":
            o = y
        elif self.out == "p-y":
            o = sat(int(p) - int(y), self.ar.WD)
        else:
            o = y if flag else int(p)
        return e, o, flag


class Engine:
    """State of one adaptive engine (accumulators, pending delayed updates, block gradient) across calls.

    engine : "lms"   exact LMS (lms_serial, lms_folded): y(n) sees every update up to n-1
             "dlms"  delayed LMS (lms_df, lms_systolic): the update of the step s is seen from step s+D+1
             "block" block LMS (lms_rowblock, lms_da): updates summed over a block, committed Dc steps after
                     its last sample (Dc = T+3 for lms_rowblock; 0 for lms_da, which stalls instead)
    """

    def __init__(self, ar: Arith, L, engine="lms", D=0, Dc=0, A=None, out="e", gate=None):
        assert engine in ("lms", "dlms", "block"), engine
        self.ar, self.L, self.engine, self.D, self.Dc = ar, L, engine, D, Dc
        self.A = np.zeros(L, np.int64) if A is None else np.array(A, np.int64)
        self.eu = ErrUnit(ar, out, gate)
        self.q = deque()
        self.G = np.zeros(L, np.int64)
        self.step = 0

    def process(self, X, d, *, adapt=None, p=None, valid=None, last=None, record=False):
        """Process a stream of steps (see run). Returns dict(out, y, e, flag) for the valid entries."""
        ar, A, q, G, eu = self.ar, self.A, self.q, self.G, self.eu
        X = np.asarray(X, np.int64)
        N = X.shape[0]
        d = np.asarray(d, np.int64)
        p = d if p is None else np.asarray(p, np.int64)
        adapt = np.ones(N, bool) if adapt is None else np.asarray(adapt, bool)
        valid = np.ones(N, bool) if valid is None else np.asarray(valid, bool)
        last = np.zeros(N, bool) if last is None else np.asarray(last, bool)
        nv = int(valid.sum())
        o = np.empty(nv, np.int64)
        ys = np.empty(nv, np.int64)
        es = np.empty(nv, np.int64)
        fl = np.zeros(nv, bool)
        hist = [] if record else None
        eng, D, Dc = self.engine, self.D, self.Dc
        i = 0
        for n in range(N):
            s = self.step
            if eng == "block":
                while q and q[0][0] <= s:
                    ar.apply(A, q.popleft()[1])
            if valid[n]:
                x = X[n]
                y = ar.filt(A, x)
                e, on, flag = eu(y, d[n], p[n])
                a = bool(adapt[n]) and not flag
                if eng == "lms":
                    if a:
                        ar.apply(A, ar.grad(e, x))
                elif eng == "dlms":
                    q.append(ar.grad(e, x) if a else None)
                else:
                    if a:
                        G += ar.grad(e, x)
                    if last[n]:
                        q.append((s + Dc + 1, G.copy()))
                        G[:] = 0
                o[i], ys[i], es[i], fl[i] = on, y, e, flag
                i += 1
                if record:
                    hist.append(A.copy())
            elif eng == "dlms":
                q.append(None)
            if eng == "dlms" and len(q) > D:
                g = q.popleft()
                if g is not None:
                    ar.apply(A, g)
            self.step += 1
        res = dict(out=o, y=ys, e=es, flag=fl)
        if record:
            res["hist"] = np.array(hist)
        return res

    def finish(self):
        """Apply everything still pending (the end of a long drain)."""
        while self.q:
            g = self.q.popleft()
            if self.engine == "block":
                g = g[1]
            if g is not None:
                self.ar.apply(self.A, g)


def run(ar: Arith, X, d, *, engine="lms", D=0, Dc=0, A=None, out="e", gate=None, **kw):
    """Run one engine over a stream of steps.

    X      : (N, L) int64 tap vectors (Q FD);  d, p : (N,) desired and pass-through samples
    adapt  : (N,) bool update enable (default all True)
    valid  : (N,) bool; a False entry is an empty pipeline step (bubble, drain or pre-roll shift): it produces
             no output and no update, but it advances the delayed updates of "dlms" and "block"
    last   : (N,) bool block ends (engine "block")
    A      : (L,) int64 initial accumulators; out, gate: see ErrUnit
    Returns dict(out, y, e, flag, A) for the valid entries (and the weight history with record=True).
    """
    X = np.asarray(X, np.int64)
    eng = Engine(ar, X.shape[1], engine, D, Dc, A, out, gate)
    res = eng.process(X, d, **kw)
    eng.finish()
    res["A"] = eng.A
    return res


# ------------------------------------------------------------------------------- engine catalogue (models)
ENGINE_CLASS = {
    "serial": "lms",
    "folded": "lms",
    "df": "dlms",
    "systolic": "dlms",
    "rowblock": "block",
    "da": "block",
}


def tree_levels(n):
    """Register levels of a binary adder tree over n inputs: ceil(log2 n), 0 for one input."""
    return int(np.ceil(np.log2(n))) if n > 1 else 0


def adaptation_delay(engine, L, tree_regs=None):
    """Adaptation delay D of the pipelined engines as built in rtl/engines (in samples).

    lms_df       : products (1) + adder-tree registers + error (1) + update product (1) -> D = tree + 3
    lms_systolic : the partial sum crosses one register per tap; D = L + 3
    """
    if engine == "df":
        t = tree_regs if tree_regs is not None else tree_levels(L)
        return t + 3
    if engine == "systolic":
        return L + 3
    return 0


def commit_delay(engine, L):
    """Steps from the last sample of a block to the step whose filter first sees the block's update, minus one."""
    if engine == "rowblock":
        return tree_levels(L) + 3
    return 0


def run_engine(name, ar, X, d, **kw):
    """Run the model of a named engine (see ENGINE_CLASS) with its adaptation or commit delay."""
    cls = ENGINE_CLASS[name]
    L = np.asarray(X).shape[1]
    if cls == "dlms":
        kw.setdefault("D", adaptation_delay(name, L))
    if cls == "block":
        kw.setdefault("Dc", commit_delay(name, L))
    return run(ar, X, d, engine=cls, **kw)
