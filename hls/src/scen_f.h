// Configuration and prototype of the F top (hls/src/scen_f.cpp).
#pragma once

#ifndef F_W
#define F_W 512
#endif
#ifndef F_H
#define F_H 512
#endif
#ifndef F_LOGNOB
#define F_LOGNOB 4          // NOB = 2^LOGNOB optical-black columns per row
#endif
#ifndef F_XSEL
#define F_XSEL 0            // 0: OB mean as reference, 1: the concurrent reference channel
#endif
#ifndef F_S
#define F_S 1
#endif

#define ENG_L 1

#include <hls_stream.h>

#include "afhls/engine_select.h"

typedef afhls::sint<16> pix_t;
typedef afhls::Fxp<F_S> F;
typedef afhls::ErrUnit<F, afhls::OUT_E, 0> EU;

// mode 0: frozen correction; 1: calibrate on every pixel (dark frames); 2: adapt on the OB pixels of each row
// (leave-one-out reference), then correct the row frozen.
void scen_f_top(hls::stream<pix_t>& pix_in, hls::stream<pix_t>& ref_in, hls::stream<pix_t>& pix_out, int mode,
                bool reset);
