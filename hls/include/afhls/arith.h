// The arithmetic contract of every engine, bit-exact with afarch/fxp.py and rtl/common/lms_arith.vh.
//
//   pixel data x, d, y, e, p   signed WD = 16 bits, FD = 12 fraction bits   (Q12)
//   weight view w              signed WW = 24 bits, FW = 20 fraction bits   (Q20)
//   accumulators               signed WA = 48 bits (a DSP48E1 P register)
//
//   g = e x                                   update product, 2 FD fraction bits
//   A <- A + g                                exact; never rounded
//   w = sat_WW(A >>> V),  V = 2 FD - FW + S   the step mu = 2^-S is a bit slice
//   y = sat_WD((2^(FW-1) + sum w x) >>> FW)   rounded once
//   e = sat_WD(d - y)
#pragma once

#include "types.h"

namespace afhls {

enum Rule { RULE_LMS = 0, RULE_SE = 1, RULE_SD = 2, RULE_SS = 3 };
enum OutMode { OUT_E = 0, OUT_Y = 1, OUT_PY = 2, OUT_GATED = 3 };

template <int S_, int RULE_ = RULE_LMS, int LEAK_ = 0, int WD_ = 16, int FD_ = 12, int WW_ = 24, int FW_ = 20,
          int WA_ = 48>
struct Fxp {
    static const int WD = WD_, FD = FD_, WW = WW_, FW = FW_, WA = WA_;
    static const int S = S_, RULE = RULE_, LEAK = LEAK_;
    static const int V = 2 * FD - FW + S;
    static_assert(V >= 1, "the view shift 2FD - FW + S must be at least 1");
    static_assert(WW <= WA - V, "the weight view must fit the accumulator");

    typedef sint<WD> data_t;      // pixels, taps, errors
    typedef sint<WW> wv_t;        // weight view
    typedef sint<WA> acc_t;       // weight and filter accumulators

    // Accumulator whose view is the weight w_q / 2^FW (w_q an integer in Q FW).
    static acc_t acc_from_wq(long long wq) { return acc_t(wq) << V; }

    static wv_t view(const acc_t& A) {
#pragma HLS INLINE
        return sat<WW>(A >> V);
    }

    static acc_t rnd() {
#pragma HLS INLINE
        return acc_t(1LL << (FW - 1));
    }

    static data_t yout(const acc_t& acc) {
#pragma HLS INLINE
        return sat<WD>(acc >> FW);
    }

    static data_t error(const data_t& d, const data_t& y) {
#pragma HLS INLINE
        return sat<WD>(sint<WD + 1>(d) - sint<WD + 1>(y));
    }

    // Update product for error e and tap x, in units of 2^-2FD (before the step).
    static acc_t grad(const data_t& e, const data_t& x) {
#pragma HLS INLINE
        if (RULE == RULE_LMS) return acc_t(sint<2 * WD>(e) * sint<2 * WD>(x));
        if (RULE == RULE_SE) return acc_t(sint<2 * WD>(sgn(e)) * (sint<2 * WD>(x) << FD));
        if (RULE == RULE_SD) return acc_t((sint<2 * WD>(e) << FD) * sint<2 * WD>(sgn(x)));
        return acc_t(sint<2 * WD + 2>(sgn(e) * sgn(x)) << (2 * FD));
    }

    // One applied update of one weight accumulator (leaky when LEAK > 0).
    static acc_t apply(const acc_t& A, const acc_t& g) {
#pragma HLS INLINE
        sint<WA + 2> a = A;
        if (LEAK) a -= (a >> LEAK);
        a += g;
        return narrow<WA>(a);
    }
};

// Robust error gate of the gated self-tuning filter (afarch.engines.Gate, rtl/common/lms_err_unit.v):
// flag when |e| > max((s >> FRAC) << KS, TMIN); on unflagged samples s <- s + (1.5|e| << FRAC - s) >> RATE.
template <int WD, int KS = 2, int RATE = 7, int FRAC = 8, int TMIN = 410, int S0 = 205>
struct Gate {
    typedef sint<WD + FRAC + 4> s_t;
    static s_t init() { return s_t(S0) << FRAC; }

    static bool step(s_t& s, const sint<WD>& e) {
#pragma HLS INLINE
        sint<WD + 1> ae = (e < 0) ? sint<WD + 1>(-sint<WD + 1>(e)) : sint<WD + 1>(e);
        s_t thr = (s >> FRAC) << KS;
        if (thr < TMIN) thr = TMIN;
        bool flag = s_t(ae) > thr;
        if (!flag) {
            s_t target = s_t(ae + (ae >> 1)) << FRAC;
            s = narrow<WD + FRAC + 4>(s + ((target - s) >> RATE));
        }
        return flag;
    }
};

// Error unit: e = sat(d - y), optional gate, output select (e | y | p - y | flag ? y : p).
template <class F, int OUT, int GATED>
struct ErrUnit {
    typedef typename F::data_t data_t;
    typedef Gate<F::WD> G;

    static void eval(const data_t& y, const data_t& d, const data_t& p, typename G::s_t& gs, data_t& e, data_t& o,
                     bool& flag) {
#pragma HLS INLINE
        e = F::error(d, y);
        flag = GATED ? G::step(gs, e) : false;
        if (OUT == OUT_E) o = e;
        else if (OUT == OUT_Y) o = y;
        else if (OUT == OUT_PY) o = sat<F::WD>(sint<F::WD + 1>(p) - sint<F::WD + 1>(y));
        else o = flag ? y : p;
    }
};

}  // namespace afhls
