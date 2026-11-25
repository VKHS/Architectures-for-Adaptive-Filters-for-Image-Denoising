// Configuration and prototype of the C top (hls/src/scen_c.cpp).
#pragma once

#ifndef C_W
#define C_W 512
#endif
#ifndef C_H
#define C_H 512
#endif
#ifndef C_L
#define C_L 128             // taps of the delayed-reference predictor
#endif
#ifndef C_DELAY
#define C_DELAY 8           // prediction delay (pixels)
#endif
#ifndef C_S
#define C_S 7
#endif

#define ENG_L C_L
#define ENG_TDL 1

#include <hls_stream.h>

#include "afhls/engine_select.h"

typedef afhls::sint<16> pix_t;
typedef afhls::Fxp<C_S> F;
typedef afhls::ErrUnit<F, afhls::OUT_PY, 0> EU;

void scen_c_top(hls::stream<pix_t>& pix_in, hls::stream<pix_t>& pix_out, bool reset);
