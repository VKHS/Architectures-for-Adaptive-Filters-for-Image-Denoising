// File I/O of the C-simulation testbenches: whitespace-separated integers in, one output line per sample out.
#pragma once

#include <cstdio>
#include <cstdlib>
#include <fstream>
#include <string>
#include <vector>

inline std::vector<long long> read_ints(const char* path) {
    std::ifstream f(path);
    if (!f) {
        std::fprintf(stderr, "cannot open %s\n", path);
        std::exit(2);
    }
    std::vector<long long> v;
    long long x;
    while (f >> x) v.push_back(x);
    return v;
}

inline FILE* open_out(const char* path) {
    FILE* f = std::fopen(path, "w");
    if (!f) {
        std::fprintf(stderr, "cannot write %s\n", path);
        std::exit(2);
    }
    return f;
}

inline void usage_if(bool bad, const char* text) {
    if (bad) {
        std::fprintf(stderr, "usage: %s\n", text);
        std::exit(2);
    }
}
