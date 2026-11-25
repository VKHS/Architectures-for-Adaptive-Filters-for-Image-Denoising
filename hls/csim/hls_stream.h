// Minimal hls::stream for C simulation with a plain C++ compiler (no Vitis HLS installation).
// Only on the include path of the g++ builds (hls/scripts/csim.sh, smoke/smoke.py); Vitis HLS uses its own
// <hls_stream.h>. A FIFO with the blocking read/write semantics of C simulation.
#pragma once

#include <cassert>
#include <cstdio>
#include <cstdlib>
#include <deque>
#include <string>

namespace hls {

template <class T>
class stream {
  public:
    stream() {}
    explicit stream(const char* name) : name_(name) {}
    stream(const stream&) = delete;
    stream& operator=(const stream&) = delete;

    void write(const T& v) { q_.push_back(v); }
    T read() {
        if (q_.empty()) {
            std::fprintf(stderr, "hls::stream '%s': read from an empty stream\n", name_.c_str());
            std::abort();
        }
        T v = q_.front();
        q_.pop_front();
        return v;
    }
    bool read_nb(T& v) {
        if (q_.empty()) return false;
        v = read();
        return true;
    }
    bool write_nb(const T& v) {
        write(v);
        return true;
    }
    void operator<<(const T& v) { write(v); }
    void operator>>(T& v) { v = read(); }
    bool empty() const { return q_.empty(); }
    bool full() const { return false; }
    std::size_t size() const { return q_.size(); }

  private:
    std::deque<T> q_;
    std::string name_ = "stream";
};

}  // namespace hls
