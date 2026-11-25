// Scenario F in HLS: reference-sensor canceller. The C++ counterpart of rtl/scenarios/scen_f_top.v.
//
// Every row arrives as NOB optical-black (OB) pixels, which see the row's offset but no light, followed by W
// scene pixels; with XSEL = 1 a reference-channel sample comes with every scene pixel.
//   x_ob = (sum of the row's OB pixels) >>> LOGNOB            one adder, no division
//   x    = XSEL ? ref : x_ob,   d = scene pixel,   out = e = d - w x
//   mode 0 frozen      no adaptation (the weight was calibrated before)
//   mode 1 calibrate   adapt on every scene pixel (run on dark frames: the scene is absent there)
//   mode 2 OB online   adapt on each OB pixel with x_k = (sum - ob_k) / (NOB - 1) (one constant multiply),
//                      then correct the scene row with the frozen weight
#include "scen_f.h"

using namespace afhls;

void scen_f_top(hls::stream<pix_t>& pix_in, hls::stream<pix_t>& ref_in, hls::stream<pix_t>& pix_out, int mode,
                bool reset) {
#pragma HLS INTERFACE mode=axis port=pix_in
#pragma HLS INTERFACE mode=axis port=ref_in
#pragma HLS INTERFACE mode=axis port=pix_out
#pragma HLS INTERFACE mode=s_axilite port=mode
#pragma HLS INTERFACE mode=s_axilite port=reset
#pragma HLS INTERFACE mode=s_axilite port=return

    const int NOB = 1 << F_LOGNOB;
    const int INV = (4096 + (NOB - 1) / 2) / (NOB - 1);   // round(2^12 / (NOB - 1))
    ENGINE_STATE()
    static EU::G::s_t gate_s;
    if (reset) {
        ENGINE_RESET(0);
        gate_s = EU::G::init();
    }
    pix_t ob[NOB];
#pragma HLS ARRAY_PARTITION variable=ob type=complete
    F::data_t x[1];
ROWS:
    for (int i = 0; i < F_H; i++) {
        sint<16 + F_LOGNOB + 2> sum = 0;
    OB:
        for (int k = 0; k < NOB; k++) {
#pragma HLS PIPELINE II=1
            ob[k] = pix_in.read();
            sum += ob[k];
        }
        if (mode == 2) {
        LOO:
            for (int k = 0; k < NOB; k++) {
                ENGINE_STEP_PIPELINE()
                x[0] = narrow<16>((sint<48>(sum - ob[k]) * INV) >> 12);
                F::data_t o;
                bool flag;
                ENGINE_STEP(true, false, x, ob[k], ob[k], true, gate_s, o, flag);
            }
        }
        const F::data_t xob = narrow<16>(sum >> F_LOGNOB);
    SCENE:
        for (int j = 0; j < F_W; j++) {
            ENGINE_STEP_PIPELINE()
            x[0] = F_XSEL ? F::data_t(ref_in.read()) : xob;
            const F::data_t d = pix_in.read();
            F::data_t o;
            bool flag;
            ENGINE_STEP(true, j == F_W - 1, x, d, d, mode == 1, gate_s, o, flag);
            pix_out.write(o);
        }
    }
    ENGINE_FINISH(x);
}
