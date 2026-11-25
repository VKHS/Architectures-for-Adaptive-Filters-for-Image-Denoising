// Scenario C in HLS: periodic interference cancelled without a reference. The C++ counterpart of
// rtl/scenarios/scen_c_top.v, bit-exact with afarch.scenarios.scenario_c.
//
// Per row, two phases on a buffered row:
//   HB      h(j) = z(j) - round(g * z)(j): 33-tap Gaussian (sigma 4, Q16 coefficients that sum to 2^16, so a
//           constant row has an exactly zero high band), reflected borders, symmetric pre-adds
//   CANCEL  the tapped delay line takes x0(t) = h(refl(t - DELAY)) for t = -(L-1) .. W-1, so that it holds the
//           reflected history x_k(j) = h(refl(j - DELAY - k)) at pixel j; d = h(j), output sat(z(j) - y)
// The first L-1 steps are pre-roll shifts: empty steps for the delayed class (they advance its pending updates),
// plain shifts for the others.
#include "scen_c.h"

using namespace afhls;

namespace {
const int GH = 16;                                      // half length of the Gaussian
const int GF = 16;                                      // its fraction bits
const int GCOEF[GH + 1] = {6536, 6335, 5768, 4934, 3965, 2993, 2122, 1414, 885,
                           520,  287,  149,  73,   33,   14,   6,    2};
}  // namespace

void scen_c_top(hls::stream<pix_t>& pix_in, hls::stream<pix_t>& pix_out, bool reset) {
#pragma HLS INTERFACE mode=axis port=pix_in
#pragma HLS INTERFACE mode=axis port=pix_out
#pragma HLS INTERFACE mode=s_axilite port=reset
#pragma HLS INTERFACE mode=s_axilite port=return

    const int W = C_W, H = C_H, L = C_L;
    static pix_t z[W];                                  // the row (dual-port block RAM)
    static pix_t h[W];                                  // its high band
    static F::data_t tdl[ENG_TDL_LEN];                  // tapped delay line, newest at 0
#pragma HLS ARRAY_PARTITION variable=tdl type=complete
    ENGINE_STATE()
    static EU::G::s_t gate_s;

    if (reset) {
        ENGINE_RESET(0);
        gate_s = EU::G::init();
        for (int k = 0; k < ENG_TDL_LEN; k++) tdl[k] = 0;
    }

ROWS:
    for (int r = 0; r < H; r++) {
    READ:
        for (int c = 0; c < W; c++) {
#pragma HLS PIPELINE II=1
            z[c] = pix_in.read();
        }

        // ---------------------------------------------------------------- HB phase: Gaussian high band
        pix_t zw[2 * GH + 1];
#pragma HLS ARRAY_PARTITION variable=zw type=complete
    HB:
        for (int t = -GH; t < W + GH; t++) {
#pragma HLS PIPELINE II=1
            for (int m = 0; m < 2 * GH; m++) {
#pragma HLS UNROLL
                zw[m] = zw[m + 1];
            }
            zw[2 * GH] = z[refl(t, W)];
            if (t >= GH) {
                const int j = t - GH;
                sint<48> lp = sint<48>(1LL << (GF - 1)) + sint<48>(GCOEF[0]) * zw[GH];
                for (int m = 1; m <= GH; m++) {
#pragma HLS UNROLL
                    lp += sint<48>(GCOEF[m]) * sint<18>(sint<17>(zw[GH - m]) + zw[GH + m]);
                }
                h[j] = sat<16>(sint<17>(z[j]) - sint<17>(lp >> GF));
            }
        }

        // ---------------------------------------------------------------- CANCEL phase
    CANCEL:
        for (int t = -(L - 1); t < W; t++) {
            ENGINE_STEP_PIPELINE()
            for (int k = ENG_TDL_LEN - 1; k > 0; k--) {
#pragma HLS UNROLL
                tdl[k] = tdl[k - 1];
            }
            tdl[0] = h[refl(t - C_DELAY, W)];
            const bool valid = t >= 0;
            const int j = valid ? t : 0;
            if (valid || ENGINE_WANTS_EMPTY_STEPS) {
                F::data_t o;
                bool flag;
                ENGINE_STEP(valid, valid && j == W - 1, tdl, h[j], z[j], true, gate_s, o, flag);
                if (valid) pix_out.write(o);
            }
        }
    }
    ENGINE_FINISH(tdl);                                 // the frame drain
}
