"""Bit-accurate models of the scenario front ends: what feeds the engines with taps.

Index reflection is numpy's whole-sample "reflect" (x[-1] = x[1], x[n] = x[n-2]); the RTL produces it with
address generators that read row buffers in a V pattern at the start of a row and a Lambda pattern at its end.
"""
import numpy as np
from numpy.lib.stride_tricks import sliding_window_view

from .fxp import sat


def refl(i, n):
    """numpy-style whole-sample reflection of index i into [0, n-1] (valid for -n < i < 2n - 1)."""
    i = np.asarray(i)
    i = np.where(i < 0, -i, i)
    return np.where(i > n - 1, 2 * (n - 1) - i, i)


# ------------------------------------------------------------------------------------------ 2-D windows
def tap_offsets(R, H):
    """Window offsets (di, dj) in tap order: row-major over [-R, R]^2 without the central (2H+1)^2 block."""
    return [(a, b) for a in range(-R, R + 1) for b in range(-R, R + 1) if max(abs(a), abs(b)) > H]


def window_taps(z, R, H):
    """(rows*cols, L) tap matrix of the blind-spot window, reflect-padded (rtl/scenarios/window_gen.v)."""
    k = 2 * R + 1
    pad = np.pad(z, R, mode="reflect")
    win = sliding_window_view(pad, (k, k)).reshape(-1, k * k)
    m = np.zeros((k, k), bool)
    for a, b in tap_offsets(R, H):
        m[a + R, b + R] = True
    return np.ascontiguousarray(win[:, m.ravel()])


# --------------------------------------------------------------------------- 1-D: high band and the TDL
def gauss_kernel(sigma=4.0, half=16, GF=16):
    """Symmetric Gaussian low-pass, coefficients in Q GF, centre adjusted so that they sum to 2^GF exactly."""
    m = np.arange(-half, half + 1)
    g = np.exp(-m ** 2 / (2.0 * sigma ** 2))
    g /= g.sum()
    q = np.round(g * (1 << GF)).astype(np.int64)
    q[half] += (1 << GF) - int(q.sum())
    return q


def highband_row(zrow, kern, GF=16, WD=16):
    """h = z - lowpass(z) along one row (Q FD in, Q FD out), reflect borders (rtl/scenarios/highband_row.v)."""
    n = len(zrow)
    half = len(kern) // 2
    idx = refl(np.arange(-half, n + half), n)
    p = np.asarray(zrow, np.int64)[idx]
    win = sliding_window_view(p, len(kern))
    lp = (win @ kern + (1 << (GF - 1))) >> GF
    return sat(np.asarray(zrow, np.int64) - lp, WD)


def tdl_stream_row(hrow, L, delay):
    """The newest-tap stream of the canceller for one row: L-1 pre-roll values, then one per pixel.

    x_0(t) = h(refl(t - delay)) for t = -(L-1) .. W-1, so that the tapped delay line holds
    x_k(j) = h(refl(j - delay - k)) at pixel j: the reflected history of the software (np.pad "reflect").
    """
    n = len(hrow)
    t = np.arange(-(L - 1), n)
    return np.asarray(hrow, np.int64)[refl(t - delay, n)]


def tdl_taps_row(hrow, L, delay):
    """(W, L) tap matrix of the delayed-reference canceller for one row."""
    s = tdl_stream_row(hrow, L, delay)
    return np.ascontiguousarray(sliding_window_view(s, L)[:, ::-1])


# ------------------------------------------------------------------------------------ A: plane waves
def phase_increments(freqs, PB=32):
    """Phase increments per row (U) and per pixel (V) of each harmonic, as PB-bit fractions of a cycle."""
    U = [int(round((u % 1.0) * (1 << PB))) % (1 << PB) for u, _ in freqs]
    V = [int(round((v % 1.0) * (1 << PB))) % (1 << PB) for _, v in freqs]
    return U, V


def cos_table(NA=10, C=1.0, FD=12):
    """Full-cycle cosine table, 2^NA entries in Q FD (one RAMB18 holds 1024 x 18 bits)."""
    a = np.arange(1 << NA)
    return np.round(C * np.cos(2 * np.pi * a / (1 << NA)) * (1 << FD)).astype(np.int64)


def plane_wave_taps(shape, freqs, NA=10, PB=32, C=1.0, FD=12):
    """(rows*cols, 2K) references [cos th_1, sin th_1, ...]: th = i U + j V (mod 2^PB), rounded to NA bits."""
    Hh, Ww = shape
    U, V = phase_increments(freqs, PB)
    tab = cos_table(NA, C, FD)
    i = np.arange(Hh, dtype=np.uint64)[:, None]
    j = np.arange(Ww, dtype=np.uint64)[None, :]
    mask = np.uint64((1 << PB) - 1)
    cols = []
    sh = np.uint64(PB - NA)
    half = np.uint64(1 << (PB - NA - 1))
    quarter = 1 << (NA - 2)
    for u, v in zip(U, V):
        th = (i * np.uint64(u) + j * np.uint64(v)) & mask
        a = (((th + half) & mask) >> sh).astype(np.int64)       # round the phase to NA bits
        cols.append(tab[a].ravel())
        cols.append(tab[(a - quarter) % (1 << NA)].ravel())    # sin th = cos(th - pi/2)
    return np.stack(cols, 1)


# ---------------------------------------------------------------------------- F: optical-black mean
def ob_mean(ob_codes, log2n):
    """Row reference of the optical-black columns: their sum >> log2(n) (n = 2^log2n columns)."""
    return np.asarray(ob_codes, np.int64).sum(axis=1) >> log2n
