// Scenario A in HLS: adaptive notch with synthetic plane-wave references on a raster stream. The C++
// counterpart of rtl/scenarios/scen_a_top.v, bit-exact with afarch.scenarios.scenario_a.
//
// Harmonic k has the phase th = i U_k + j V_k (mod 2^32) at pixel (i, j): two accumulators per harmonic, no
// multiplier. The phase is rounded to NA = 10 bits and read from a 1024-entry cosine ROM; sin th is the same
// table 256 entries back. As in the RTL, every harmonic owns a copy of the table, read through its two ports
// (cos and sin): one RAMB18 per harmonic. The 2K references and the centred pixel d = pixel - off go to the
// engine, whose error is the output (+ off).
#include "scen_a.h"

using namespace afhls;

namespace {
const int NA = 10;

// One ROM per harmonic: every instantiation of the template is a separate table.
template <int k>
struct CosRom {
    static const short t[1 << NA];
};
template <int k>
const short CosRom<k>::t[1 << NA] = {
#include "afhls/cos1024_q12.inc"
};

static_assert(A_K >= 1 && A_K <= 4, "A_K = 1 .. 4 harmonics");

inline short cos_rom(int k, int a) {
#pragma HLS INLINE
    switch (k) {
        case 0: return CosRom<0>::t[a];
        case 1: return CosRom<1>::t[a];
        case 2: return CosRom<2>::t[a];
        default: return CosRom<3>::t[a];
    }
}
}  // namespace

void scen_a_top(hls::stream<pix_t>& pix_in, hls::stream<pix_t>& pix_out, pix_t off, const phase_t uinc[A_K],
                const phase_t vinc[A_K], bool reset) {
#pragma HLS INTERFACE mode=axis port=pix_in
#pragma HLS INTERFACE mode=axis port=pix_out
#pragma HLS INTERFACE mode=s_axilite port=off
#pragma HLS INTERFACE mode=s_axilite port=uinc
#pragma HLS INTERFACE mode=s_axilite port=vinc
#pragma HLS INTERFACE mode=s_axilite port=reset
#pragma HLS INTERFACE mode=s_axilite port=return

    const int W = A_W, H = A_H, K = A_K;
    const phase_t HALF = phase_t(1ULL << (32 - NA - 1));   // rounds the phase to NA bits
    ENGINE_STATE()
    static EU::G::s_t gate_s;
    if (reset) {
        ENGINE_RESET(0);
        gate_s = EU::G::init();
    }

    phase_t rowph[K], pixph[K];
#pragma HLS ARRAY_PARTITION variable=rowph type=complete
#pragma HLS ARRAY_PARTITION variable=pixph type=complete
    for (int k = 0; k < K; k++) rowph[k] = 0;              // every frame starts at phase 0

    F::data_t x[ENG_L];
#pragma HLS ARRAY_PARTITION variable=x type=complete
ROWS:
    for (int i = 0; i < H; i++) {
        for (int k = 0; k < K; k++) pixph[k] = rowph[k];
    COLS:
        for (int j = 0; j < W; j++) {
            ENGINE_STEP_PIPELINE()
            for (int k = 0; k < K; k++) {
#pragma HLS UNROLL
                const int a = int(ll(add_wrap<32>(pixph[k], HALF)) >> (32 - NA));
                x[2 * k] = cos_rom(k, a);
                x[2 * k + 1] = cos_rom(k, (a - (1 << (NA - 2))) & ((1 << NA) - 1));
                pixph[k] = add_wrap<32>(pixph[k], vinc[k]);
            }
            const F::data_t d = narrow<16>(sint<17>(pix_in.read()) - off);
            F::data_t o;
            bool flag;
            ENGINE_STEP(true, j == W - 1, x, d, d, true, gate_s, o, flag);
            pix_out.write(sat<16>(sint<17>(o) + off));
        }
        for (int k = 0; k < K; k++) rowph[k] = add_wrap<32>(rowph[k], uinc[k]);
    }
    ENGINE_FINISH(x);
}
