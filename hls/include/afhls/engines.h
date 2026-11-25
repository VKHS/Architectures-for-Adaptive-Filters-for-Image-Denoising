// The three algorithmic classes of the six RTL engines, as HLS function templates.
//
//   exact LMS    (lms_serial, lms_folded)     y(n) uses every update up to n-1
//   delayed LMS  (lms_df: D = ceil(log2 L)+3, lms_systolic: D = L+3)   y(n) uses the updates up to n-1-D
//   block LMS    (lms_rowblock, lms_da)       weights frozen along a row, one summed update at its end
//
// Each class is bit-exact with afarch.engines.Engine for the same step stream. The state is passed in as
// arrays that the top function declares (static, with its partitioning pragmas, see engine_select.h), as Vitis
// HLS wants array pragmas inside the function that defines the array. A step is either a valid sample or an
// empty step (pre-roll shift or drain), which only the delayed class needs: it advances the pending updates.
#pragma once

#include "arith.h"

namespace afhls {

enum EngineClass { CLASS_EXACT = 0, CLASS_DELAYED = 1, CLASS_BLOCK = 2 };

// ------------------------------------------------------------------------------------------------ exact LMS
// Folded schedule of lms_folded with P lanes: in the pass of sample n each lane first applies the pending
// update of sample n-1 to a weight and then filters with it, so one pass of ceil(L/P) cycles does both halves
// of the loop. P = 1 is the one-multiplier-per-half engine (the numbers of lms_serial).
template <class F, int L>
void exact_reset(typename F::acc_t A[L], typename F::data_t& pe, bool& pend, typename F::acc_t a0) {
    for (int k = 0; k < L; k++) A[k] = a0;
    pe = 0;
    pend = false;
}

template <class F, int L, int P, class EU>
void exact_step(typename F::acc_t A[L], typename F::data_t px[L], typename F::data_t& pe, bool& pend,
                const typename F::data_t x[L], typename F::data_t d, typename F::data_t p, bool adapt,
                typename EU::G::s_t& gs, typename F::data_t& o, bool& flag) {
#pragma HLS INLINE
    typedef typename F::acc_t acc_t;
    typedef typename F::data_t data_t;
    const int M = (L + P - 1) / P;
    acc_t lane[P];
#pragma HLS ARRAY_PARTITION variable=lane type=complete
    for (int q = 0; q < P; q++) {
#pragma HLS UNROLL
        lane[q] = (q == 0) ? F::rnd() : acc_t(0);
    }
FUSED:
    for (int m = 0; m < M; m++) {
#pragma HLS PIPELINE II=1
        for (int q = 0; q < P; q++) {
#pragma HLS UNROLL
            const int k = m * P + q;
            if (k < L) {
                acc_t a = A[k];
                if (pend) a = F::apply(a, F::grad(pe, px[k]));
                A[k] = a;
                lane[q] = narrow<F::WA>(lane[q] + acc_t(F::view(a) * x[k]));
                px[k] = x[k];
            }
        }
    }
    acc_t acc = 0;
    for (int q = 0; q < P; q++) {
#pragma HLS UNROLL
        acc = narrow<F::WA>(acc + lane[q]);
    }
    data_t y = F::yout(acc), e;
    EU::eval(y, d, p, gs, e, o, flag);
    pend = adapt && !flag;
    pe = e;
}

template <class F, int L>
void exact_finish(typename F::acc_t A[L], const typename F::data_t px[L], typename F::data_t pe, bool& pend) {
    if (pend)
        for (int k = 0; k < L; k++) A[k] = F::apply(A[k], F::grad(pe, px[k]));
    pend = false;
}

// ---------------------------------------------------------------------------------------------- delayed LMS
// One step per clock (II = 1): every tap has its filter multiplier and its update multiplier. The update of
// step s is applied at the end of step s + D, so the filter sees it from step s + D + 1. A shift register of D
// slots holds (adapt, e, taps) of the last D steps, newest in slot 0; forming g = e x when an entry leaves
// gives the bits of queueing g itself. Because the queue is a register chain, the scheduler sees the true
// dependence distance: the loop pipelines at II = 1 whenever its latency fits in D + 1 cycles, and its
// initiation interval grows (it never produces wrong bits) when it does not.
template <class F, int L, int D>
void delayed_reset(typename F::acc_t A[L], bool aq[D], typename F::acc_t a0) {
    static_assert(D >= 1, "the delayed class needs D >= 1 (D = 0 is the exact class)");
    for (int k = 0; k < L; k++) A[k] = a0;
    for (int i = 0; i < D; i++) aq[i] = false;
}

// Vector form: the taps of every step are kept with it (window front ends, D and E).
template <class F, int L, int D, class EU>
void delayed_step(typename F::acc_t A[L], typename F::data_t xq[D][L], typename F::data_t eq[D], bool aq[D],
                  bool valid, const typename F::data_t x[L], typename F::data_t d, typename F::data_t p,
                  bool adapt, typename EU::G::s_t& gs, typename F::data_t& o, bool& flag) {
#pragma HLS INLINE
    typedef typename F::acc_t acc_t;
    typedef typename F::data_t data_t;
    const bool a_old = aq[D - 1];                         // the entry of step s - D leaves the queue
    const data_t e_old = eq[D - 1];
    data_t x_old[L];
#pragma HLS ARRAY_PARTITION variable=x_old type=complete
    for (int k = 0; k < L; k++) {
#pragma HLS UNROLL
        x_old[k] = xq[D - 1][k];
    }
    data_t e = 0;
    flag = false;
    if (valid) {                                          // filter with the updates up to step s - 1 - D
        acc_t acc = F::rnd();
        for (int k = 0; k < L; k++) {
#pragma HLS UNROLL
            acc = narrow<F::WA>(acc + acc_t(F::view(A[k]) * x[k]));
        }
        data_t y = F::yout(acc);
        EU::eval(y, d, p, gs, e, o, flag);
    }
    for (int i = D - 1; i > 0; i--) {                     // shift the queue
#pragma HLS UNROLL
        aq[i] = aq[i - 1];
        eq[i] = eq[i - 1];
        for (int k = 0; k < L; k++) {
#pragma HLS UNROLL
            xq[i][k] = xq[i - 1][k];
        }
    }
    aq[0] = valid && adapt && !flag;
    eq[0] = e;
    for (int k = 0; k < L; k++) {
#pragma HLS UNROLL
        xq[0][k] = x[k];
    }
    if (a_old) {                                          // apply the update of step s - D
        for (int k = 0; k < L; k++) {
#pragma HLS UNROLL
            A[k] = F::apply(A[k], F::grad(e_old, x_old[k]));
        }
    }
}

template <class F, int L, int D>
void delayed_finish(typename F::acc_t A[L], typename F::data_t xq[D][L], typename F::data_t eq[D], bool aq[D]) {
    for (int i = D - 1; i >= 0; i--) {                    // the oldest pending update first
        if (aq[i])
            for (int k = 0; k < L; k++) A[k] = F::apply(A[k], F::grad(eq[i], xq[i][k]));
        aq[i] = false;
    }
}

// Tapped-delay-line form (scenario C): the caller shifts one newest tap per step into tdl[0 .. L+D-1], so the
// taps of step s - D are tdl[D .. D+L-1] and only (adapt, e) need to be queued: one chain of L + D words, as in
// lms_df and lms_systolic with TDL = 1.
template <class F, int L, int D, class EU>
void delayed_step_tdl(typename F::acc_t A[L], typename F::data_t eq[D], bool aq[D], bool valid,
                      const typename F::data_t tdl[L + D], typename F::data_t d, typename F::data_t p, bool adapt,
                      typename EU::G::s_t& gs, typename F::data_t& o, bool& flag) {
#pragma HLS INLINE
    typedef typename F::acc_t acc_t;
    typedef typename F::data_t data_t;
    const bool a_old = aq[D - 1];
    const data_t e_old = eq[D - 1];
    data_t e = 0;
    flag = false;
    if (valid) {
        acc_t acc = F::rnd();
        for (int k = 0; k < L; k++) {
#pragma HLS UNROLL
            acc = narrow<F::WA>(acc + acc_t(F::view(A[k]) * tdl[k]));
        }
        data_t y = F::yout(acc);
        EU::eval(y, d, p, gs, e, o, flag);
    }
    for (int i = D - 1; i > 0; i--) {
#pragma HLS UNROLL
        aq[i] = aq[i - 1];
        eq[i] = eq[i - 1];
    }
    aq[0] = valid && adapt && !flag;
    eq[0] = e;
    if (a_old) {
        for (int k = 0; k < L; k++) {
#pragma HLS UNROLL
            A[k] = F::apply(A[k], F::grad(e_old, tdl[D + k]));
        }
    }
}

template <class F, int L, int D>
void delayed_finish_tdl(typename F::acc_t A[L], typename F::data_t eq[D], bool aq[D],
                        const typename F::data_t tdl[L + D]) {
    for (int i = D - 1; i >= 0; i--) {                    // slot i holds step s - i, its taps are tdl[i .. i+L-1]
        if (aq[i])
            for (int k = 0; k < L; k++) A[k] = F::apply(A[k], F::grad(eq[i], tdl[i + k]));
        aq[i] = false;
    }
}

// ------------------------------------------------------------------------------------------------ block LMS
// The filter uses weights frozen along the block (a row); a gradient accumulator per tap sums the row's updates
// and the row's last sample commits them. There is no feedback inside a row: the step pipelines at II = 1.
template <class F, int L>
void block_reset(typename F::acc_t A[L], typename F::acc_t G[L], typename F::acc_t a0) {
    for (int k = 0; k < L; k++) {
        A[k] = a0;
        G[k] = 0;
    }
}

template <class F, int L, class EU>
void block_step(typename F::acc_t A[L], typename F::acc_t G[L], bool valid, bool last,
                const typename F::data_t x[L], typename F::data_t d, typename F::data_t p, bool adapt,
                typename EU::G::s_t& gs, typename F::data_t& o, bool& flag) {
#pragma HLS INLINE
    typedef typename F::acc_t acc_t;
    typedef typename F::data_t data_t;
    flag = false;
    if (!valid) return;
    acc_t acc = F::rnd();
    for (int k = 0; k < L; k++) {
#pragma HLS UNROLL
        acc = narrow<F::WA>(acc + acc_t(F::view(A[k]) * x[k]));
    }
    data_t y = F::yout(acc), e;
    EU::eval(y, d, p, gs, e, o, flag);
    const bool a = adapt && !flag;
    for (int k = 0; k < L; k++) {
#pragma HLS UNROLL
        acc_t g = a ? acc_t(narrow<F::WA>(G[k] + F::grad(e, x[k]))) : G[k];
        if (last) {
            A[k] = F::apply(A[k], g);
            G[k] = 0;
        } else {
            G[k] = g;
        }
    }
}

}  // namespace afhls
