// Engine selection for the scenario tops, by the same number as the RTL parameter ENGINE:
//
//   ENGINE 0  lms_serial    exact LMS, P = 1              ENGINE 3  lms_systolic  delayed LMS, D = L + 3
//   ENGINE 1  lms_folded    exact LMS, ENG_P lanes        ENGINE 4  lms_rowblock  block LMS
//   ENGINE 2  lms_df        delayed LMS, D = T + 3        ENGINE 5  lms_da        block LMS
//
// Before including this header a top defines ENG_L (taps, a literal), optionally ENG_P (lanes) and ENG_TDL
// (1 when the taps come from a tapped delay line, scenario C), and after it the types F (fixed point) and EU
// (error unit). Inside the top function ENGINE_STATE() declares the static engine state with its partitioning
// pragmas; ENGINE_RESET, ENGINE_STEP and ENGINE_FINISH drive it. ENGINE_WANTS_EMPTY_STEPS is 1 for the class
// that must see the empty steps (pre-roll shifts, drains) of the RTL step stream. With ENG_TDL the taps
// argument is the delay line itself, ENG_TDL_LEN words long (L + D for the delayed class, L otherwise).
#pragma once

#include "engines.h"

#ifndef ENGINE
#define ENGINE 0
#endif
#ifndef ENG_P
#define ENG_P 1
#endif
#ifndef ENG_TDL
#define ENG_TDL 0
#endif

#define AFHLS_STR2(x) #x
#define AFHLS_STR(x) AFHLS_STR2(x)
#define AFHLS_PRAGMA(x) _Pragma(AFHLS_STR(x))

namespace afhls {
constexpr int clog2(int n) { return n <= 1 ? 0 : 1 + clog2((n + 1) / 2); }
}

// ------------------------------------------------------------------------------------------------ exact LMS
#if ENGINE == 0 || ENGINE == 1
#define ENG_CLASS 0
#if ENGINE == 0
#define ENG_LANES 1
#else
#define ENG_LANES ENG_P
#endif
#define ENGINE_WANTS_EMPTY_STEPS 0
#define ENG_TDL_LEN ENG_L
#define ENGINE_STATE()                                                              \
    static F::acc_t eng_A[ENG_L];                                                   \
    static F::data_t eng_px[ENG_L];                                                 \
    static F::data_t eng_pe;                                                        \
    static bool eng_pend;                                                           \
    AFHLS_PRAGMA(HLS ARRAY_PARTITION variable=eng_A type=cyclic factor=ENG_LANES)   \
    AFHLS_PRAGMA(HLS ARRAY_PARTITION variable=eng_px type=cyclic factor=ENG_LANES)
#define ENGINE_RESET(a0) afhls::exact_reset<F, ENG_L>(eng_A, eng_pe, eng_pend, a0)
#define ENGINE_STEP(valid, last, x, d, p, adapt, gs, o, flag)                                               \
    do {                                                                                                    \
        if (valid)                                                                                          \
            afhls::exact_step<F, ENG_L, ENG_LANES, EU>(eng_A, eng_px, eng_pe, eng_pend, x, d, p, adapt, gs, \
                                                        o, flag);                                           \
    } while (0)
#define ENGINE_FINISH(x) afhls::exact_finish<F, ENG_L>(eng_A, eng_px, eng_pe, eng_pend)

// ---------------------------------------------------------------------------------------------- delayed LMS
#elif ENGINE == 2 || ENGINE == 3
#define ENG_CLASS 1
#if ENGINE == 2
#define ENG_D (afhls::clog2(ENG_L) + 3)
#else
#define ENG_D (ENG_L + 3)
#endif
#define ENGINE_WANTS_EMPTY_STEPS 1
#if ENG_TDL
#define ENG_TDL_LEN (ENG_L + ENG_D)
#define ENGINE_STATE()                                                              \
    static F::acc_t eng_A[ENG_L];                                                   \
    static F::data_t eng_eq[ENG_D];                                                 \
    static bool eng_aq[ENG_D];                                                      \
    AFHLS_PRAGMA(HLS ARRAY_PARTITION variable=eng_A type=complete)                  \
    AFHLS_PRAGMA(HLS ARRAY_PARTITION variable=eng_eq type=complete)                 \
    AFHLS_PRAGMA(HLS ARRAY_PARTITION variable=eng_aq type=complete)
#define ENGINE_RESET(a0) afhls::delayed_reset<F, ENG_L, ENG_D>(eng_A, eng_aq, a0)
#define ENGINE_STEP(valid, last, x, d, p, adapt, gs, o, flag) \
    afhls::delayed_step_tdl<F, ENG_L, ENG_D, EU>(eng_A, eng_eq, eng_aq, valid, x, d, p, adapt, gs, o, flag)
#define ENGINE_FINISH(x) afhls::delayed_finish_tdl<F, ENG_L, ENG_D>(eng_A, eng_eq, eng_aq, x)
#else
#define ENG_TDL_LEN ENG_L
#define ENGINE_STATE()                                                              \
    static F::acc_t eng_A[ENG_L];                                                   \
    static F::data_t eng_xq[ENG_D][ENG_L];                                          \
    static F::data_t eng_eq[ENG_D];                                                 \
    static bool eng_aq[ENG_D];                                                      \
    AFHLS_PRAGMA(HLS ARRAY_PARTITION variable=eng_A type=complete)                  \
    AFHLS_PRAGMA(HLS ARRAY_PARTITION variable=eng_xq type=complete dim=0)           \
    AFHLS_PRAGMA(HLS ARRAY_PARTITION variable=eng_eq type=complete)                 \
    AFHLS_PRAGMA(HLS ARRAY_PARTITION variable=eng_aq type=complete)
#define ENGINE_RESET(a0) afhls::delayed_reset<F, ENG_L, ENG_D>(eng_A, eng_aq, a0)
#define ENGINE_STEP(valid, last, x, d, p, adapt, gs, o, flag) \
    afhls::delayed_step<F, ENG_L, ENG_D, EU>(eng_A, eng_xq, eng_eq, eng_aq, valid, x, d, p, adapt, gs, o, flag)
#define ENGINE_FINISH(x) afhls::delayed_finish<F, ENG_L, ENG_D>(eng_A, eng_xq, eng_eq, eng_aq)
#endif

// ------------------------------------------------------------------------------------------------ block LMS
#elif ENGINE == 4 || ENGINE == 5
#define ENG_CLASS 2
#define ENGINE_WANTS_EMPTY_STEPS 0
#define ENG_TDL_LEN ENG_L
#define ENGINE_STATE()                                                              \
    static F::acc_t eng_A[ENG_L];                                                   \
    static F::acc_t eng_G[ENG_L];                                                   \
    AFHLS_PRAGMA(HLS ARRAY_PARTITION variable=eng_A type=complete)                  \
    AFHLS_PRAGMA(HLS ARRAY_PARTITION variable=eng_G type=complete)
#define ENGINE_RESET(a0) afhls::block_reset<F, ENG_L>(eng_A, eng_G, a0)
#define ENGINE_STEP(valid, last, x, d, p, adapt, gs, o, flag) \
    afhls::block_step<F, ENG_L, EU>(eng_A, eng_G, valid, last, x, d, p, adapt, gs, o, flag)
#define ENGINE_FINISH(x) \
    do {                 \
    } while (0)

#else
#error "ENGINE must be 0 .. 5"
#endif

// The step loop of the pipelined classes runs one step per clock; the exact class pipelines its own pass.
#if ENG_CLASS == 0
#define ENGINE_STEP_PIPELINE()
#else
#define ENGINE_STEP_PIPELINE() AFHLS_PRAGMA(HLS PIPELINE II=1)
#endif
