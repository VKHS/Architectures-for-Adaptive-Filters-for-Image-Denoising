// Configuration and prototype of the D / E top (hls/src/scen_de.cpp).
#pragma once

#ifndef DE_W
#define DE_W 512
#endif
#ifndef DE_H
#define DE_H 512
#endif
#ifndef DE_R
#define DE_R 2              // window radius: 5 x 5 (D), 7 x 7 or 11 x 11 (E)
#endif
#ifndef DE_HOLE
#define DE_HOLE 0           // blind-spot radius: (2 HOLE + 1)^2 centre pixels left out
#endif
#ifndef DE_S
#define DE_S 8              // step mu = 2^-S
#endif
#ifndef DE_RULE
#define DE_RULE 0
#endif
#ifndef DE_LEAK
#define DE_LEAK 0
#endif
#ifndef DE_GATED
#define DE_GATED 0          // 1: the gated D (robust gate, output flag ? y : d)
#endif

#define ENG_L ((2 * DE_R + 1) * (2 * DE_R + 1) - (2 * DE_HOLE + 1) * (2 * DE_HOLE + 1))

#include <hls_stream.h>

#include "afhls/engine_select.h"

typedef afhls::sint<16> pix_t;
typedef afhls::Fxp<DE_S, DE_RULE, DE_LEAK> F;
typedef afhls::ErrUnit<F, DE_GATED ? afhls::OUT_GATED : afhls::OUT_Y, DE_GATED> EU;

void scen_de_top(hls::stream<pix_t>& tap_in, hls::stream<pix_t>& d_in, hls::stream<pix_t>& pix_out,
                 hls::stream<bool>& flag_out, pix_t off, long long a0_wq, bool reset);
