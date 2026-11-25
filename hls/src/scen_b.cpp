// Scenario B in HLS: the bias (drift) canceller along every row. The C++ counterpart of
// rtl/scenarios/scen_b_top.v, bit-exact with afarch.scenarios.bias_run.
//
// One weight on the constant reference x = 1: the multiplier disappears and the weight is the bias b itself.
//   Bacc has FD + S fraction bits;  b = sat(Bacc >>> S);  e = sat(d - b) is the output
//   MODE 0 LMS        Bacc += e
//   MODE 1 sign-error Bacc += sgn(e) << SK      (b moves 2^(SK-S) codes per pixel: tracks the median)
//   MODE 2 gated      Bacc += e if |e| < TAU   (adapts on the background only)
// The first pixel of every row loads b = d. The loop Bacc -> b -> e -> Bacc holds one register: II = 1.
#include "scen_b.h"

using namespace afhls;

void scen_b_top(hls::stream<pix_t>& pix_in, hls::stream<pix_t>& pix_out, hls::stream<pix_t>& bias_out) {
#pragma HLS INTERFACE mode=axis port=pix_in
#pragma HLS INTERFACE mode=axis port=pix_out
#pragma HLS INTERFACE mode=axis port=bias_out
#pragma HLS INTERFACE mode=s_axilite port=return

    const int WB = 16 + B_S + 2;
    sint<WB> bacc = 0;
ROWS:
    for (int i = 0; i < B_H; i++) {
    COLS:
        for (int j = 0; j < B_W; j++) {
#pragma HLS PIPELINE II=1
            const pix_t d = pix_in.read();
            const sint<WB> be = (j == 0) ? sint<WB>(sint<WB>(d) << B_S) : bacc;   // row start: b = d
            const pix_t b = sat<16>(be >> B_S);
            const pix_t e = sat<16>(sint<17>(d) - sint<17>(b));
            sint<WB> step;
            if (B_MODE == 0) step = e;
            else if (B_MODE == 1) step = sint<WB>(sgn(e)) * sint<WB>(1 << B_SK);
            else {
                const sint<17> ae = (e < 0) ? sint<17>(-sint<17>(e)) : sint<17>(e);
                step = (ae < B_TAU) ? sint<WB>(e) : sint<WB>(0);
            }
            bacc = narrow<WB>(be + step);
            pix_out.write(e);
            bias_out.write(b);
        }
    }
}
