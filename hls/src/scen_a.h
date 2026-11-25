// Configuration and prototype of the A top (hls/src/scen_a.cpp).
#pragma once

#ifndef A_W
#define A_W 512
#endif
#ifndef A_H
#define A_H 512
#endif
#ifndef A_K
#define A_K 2               // harmonics: L = 2K taps (cos, sin)
#endif
#ifndef A_S
#define A_S 16
#endif

#define ENG_L (2 * A_K)

#include <hls_stream.h>

#include "afhls/engine_select.h"

typedef afhls::sint<16> pix_t;
typedef afhls::uint<32> phase_t;
typedef afhls::Fxp<A_S> F;
typedef afhls::ErrUnit<F, afhls::OUT_E, 0> EU;

void scen_a_top(hls::stream<pix_t>& pix_in, hls::stream<pix_t>& pix_out, pix_t off, const phase_t uinc[A_K],
                const phase_t vinc[A_K], bool reset);
