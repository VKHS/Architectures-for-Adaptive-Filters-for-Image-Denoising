// Configuration and prototype of the B top (hls/src/scen_b.cpp).
#pragma once

#ifndef B_W
#define B_W 512
#endif
#ifndef B_H
#define B_H 512
#endif
#ifndef B_S
#define B_S 4               // mu = 2^-S
#endif
#ifndef B_MODE
#define B_MODE 2            // 0 LMS, 1 sign-error, 2 gated
#endif
#ifndef B_SK
#define B_SK 6              // sign-error step: b moves 2^(SK - S) codes per pixel
#endif
#ifndef B_TAU
#define B_TAU 328           // gate threshold in codes (0.08)
#endif

#include <hls_stream.h>

#include "afhls/types.h"

typedef afhls::sint<16> pix_t;

void scen_b_top(hls::stream<pix_t>& pix_in, hls::stream<pix_t>& pix_out, hls::stream<pix_t>& bias_out);
