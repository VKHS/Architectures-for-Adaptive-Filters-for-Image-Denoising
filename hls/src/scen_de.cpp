// Scenarios D and E in HLS: blind-spot predictor (self-tuning filter / adaptive line enhancer) on a raster
// stream. The C++ counterpart of rtl/scenarios/scen_de_top.v, bit-exact with afarch.scenarios.scenario_de.
//
//   pixel - off -> line buffers (2R+2 rows, reflected addressing) -> (2R+1)^2 window without the (2H+1)^2
//   blind spot -> engine (ENGINE 0..5) -> y, or flag ? y : d (gated D) -> + off
//
// One call processes one frame (one pass). Two planes enter, as in the RTL: the tap source and the desired
// pixel; the gated D takes the taps of a later pass from the previous pass's output. The engine state persists
// across calls (the weights carry over from pass to pass and from frame to frame); reset = 1 restarts it.
//
// Compile-time configuration (defaults in scen_de.h): DE_W, DE_H, DE_R, DE_HOLE, DE_S, DE_RULE, DE_LEAK,
// DE_GATED, ENGINE, ENG_P.
#include "scen_de.h"

using namespace afhls;

void scen_de_top(hls::stream<pix_t>& tap_in, hls::stream<pix_t>& d_in, hls::stream<pix_t>& pix_out,
                 hls::stream<bool>& flag_out, pix_t off, long long a0_wq, bool reset) {
#pragma HLS INTERFACE mode=axis port=tap_in
#pragma HLS INTERFACE mode=axis port=d_in
#pragma HLS INTERFACE mode=axis port=pix_out
#pragma HLS INTERFACE mode=axis port=flag_out
#pragma HLS INTERFACE mode=s_axilite port=off
#pragma HLS INTERFACE mode=s_axilite port=a0_wq
#pragma HLS INTERFACE mode=s_axilite port=reset
#pragma HLS INTERFACE mode=s_axilite port=return

    const int R = DE_R, K = 2 * DE_R + 1, NB = 2 * DE_R + 2, W = DE_W, H = DE_H;

    // line buffers of the two planes (centred codes): one block RAM per row buffer
    static pix_t lbt[NB][W];
    static pix_t lbd[NB][W];
#pragma HLS ARRAY_PARTITION variable=lbt type=complete dim=1
#pragma HLS ARRAY_PARTITION variable=lbd type=complete dim=1

    ENGINE_STATE()
    static EU::G::s_t gate_s;

    if (reset) {
        ENGINE_RESET(F::acc_from_wq(a0_wq));
        gate_s = EU::G::init();
    }

    // the first R + 1 rows (output row 0 needs rows up to min(R, H - 1))
PROLOGUE:
    for (int r = 0; r <= R && r < H; r++) {
        for (int c = 0; c < W; c++) {
#pragma HLS PIPELINE II=1
            lbt[r % NB][c] = narrow<16>(sint<17>(tap_in.read()) - off);
            lbd[r % NB][c] = narrow<16>(sint<17>(d_in.read()) - off);
        }
    }

ROWS:
    for (int i = 0; i < H; i++) {
        const int nr = i + R + 1;                       // the row that streams in during this output row
        const bool rd = nr < H;
        int wrow[K];                                    // buffer of every window row: refl(i + a)
#pragma HLS ARRAY_PARTITION variable=wrow type=complete
        for (int a = 0; a < K; a++) wrow[a] = refl(i + a - R, H) % NB;
        pix_t win[K][K];                                // the (2R+1) x (2R+1) register window
#pragma HLS ARRAY_PARTITION variable=win type=complete dim=0
    COLS:
        for (int t = 0; t < W + 2 * R; t++) {
            ENGINE_STEP_PIPELINE()
            if (rd && t < W) {                          // write the next row into the spare buffer
                lbt[nr % NB][t] = narrow<16>(sint<17>(tap_in.read()) - off);
                lbd[nr % NB][t] = narrow<16>(sint<17>(d_in.read()) - off);
            }
            const int c = refl(t - R, W);               // reflected column address: V and Lambda patterns
            for (int a = 0; a < K; a++) {
#pragma HLS UNROLL
                for (int b = 0; b < K - 1; b++) {
#pragma HLS UNROLL
                    win[a][b] = win[a][b + 1];
                }
                win[a][K - 1] = lbt[wrow[a]][c];
            }
            if (t >= 2 * R) {
                const int j = t - 2 * R;
                F::data_t x[ENG_L];
#pragma HLS ARRAY_PARTITION variable=x type=complete
                int n = 0;
                for (int a = 0; a < K; a++) {           // taps in row-major order, the blind spot left out
#pragma HLS UNROLL
                    for (int b = 0; b < K; b++) {
#pragma HLS UNROLL
                        const int da = a - R < 0 ? R - a : a - R, db = b - R < 0 ? R - b : b - R;
                        if ((da > db ? da : db) > DE_HOLE) x[n++] = win[a][b];
                    }
                }
                const F::data_t d = lbd[i % NB][j];
                F::data_t o;
                bool flag;
                ENGINE_STEP(true, j == W - 1, x, d, d, true, gate_s, o, flag);
                pix_out.write(sat<16>(sint<17>(o) + off));
                flag_out.write(flag);
            }
        }
    }
    ENGINE_FINISH(x);                                   // the frame drain: every pending update lands
}
