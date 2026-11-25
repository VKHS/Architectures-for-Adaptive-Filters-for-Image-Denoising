// Number types of the HLS implementation.
//
// With AFHLS_AP_TYPES defined (Vitis HLS; or C simulation with the ap_int headers on the include path) every
// signal is an ap_int of its exact width, as the synthesized hardware has it. Without it, C simulation uses
// 64-bit integers. Both give identical results because no value is ever allowed to exceed its declared width:
// every narrowing goes through sat<W>() or narrow<W>(), and narrow<W>() asserts the range in 64-bit mode.
// Phase accumulators, the only quantities that wrap on purpose, are masked explicitly.
#pragma once

#include <cassert>
#include <cstdint>

#if defined(AFHLS_AP_TYPES) || defined(__SYNTHESIS__)
#include <ap_int.h>
#define AFHLS_USE_AP 1
#else
#define AFHLS_USE_AP 0
#endif

namespace afhls {

#if AFHLS_USE_AP
template <int W> using sint = ap_int<W>;
template <int W> using uint = ap_uint<W>;
template <int W> inline long long ll(const ap_int<W>& v) { return v.to_int64(); }
template <int W> inline long long ll(const ap_uint<W>& v) { return (long long)v.to_uint64(); }
#else
template <int W> using sint = int64_t;
template <int W> using uint = uint64_t;
#endif
inline long long ll(long long v) { return v; }
inline long long ll(long v) { return v; }
inline long long ll(int v) { return v; }
inline long long ll(unsigned long long v) { return (long long)v; }
inline long long ll(unsigned long v) { return (long long)v; }

// Largest and smallest value of a W-bit two's complement word.
template <int W> constexpr long long smax() { return (1LL << (W - 1)) - 1; }
template <int W> constexpr long long smin() { return -(1LL << (W - 1)); }

// Signed saturation to W bits.
template <int W, class T>
inline sint<W> sat(const T& v) {
#pragma HLS INLINE
    if (v > smax<W>()) return sint<W>(smax<W>());
    if (v < smin<W>()) return sint<W>(smin<W>());
    return sint<W>(v);
}

// Narrowing that must never lose information (checked in 64-bit C simulation).
template <int W, class T>
inline sint<W> narrow(const T& v) {
#pragma HLS INLINE
#if !AFHLS_USE_AP
    assert(ll(v) <= smax<W>() && ll(v) >= smin<W>() && "value exceeds its declared width");
#endif
    return sint<W>(v);
}

// Sign of a value: -1, 0 or +1.
template <class T>
inline int sgn(const T& v) {
#pragma HLS INLINE
    return (v > 0) ? 1 : ((v < 0) ? -1 : 0);
}

// Unsigned W-bit addition modulo 2^W (phase accumulators wrap on purpose).
template <int W>
inline uint<W> add_wrap(const uint<W>& a, const uint<W>& b) {
#pragma HLS INLINE
#if AFHLS_USE_AP
    return a + b;
#else
    return (a + b) & ((W >= 64) ? ~0ULL : ((1ULL << W) - 1));
#endif
}

// numpy-style whole-sample reflection of an index into [0, n-1] (valid for -n < i < 2n - 1).
inline int refl(int i, int n) {
#pragma HLS INLINE
    if (i < 0) i = -i;
    if (i > n - 1) i = 2 * (n - 1) - i;
    return i;
}

}  // namespace afhls
