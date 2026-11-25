// C-simulation testbench of scen_a_top: streams an image PASSES times (the weights carry over). Writes one
// output pixel per line, every pass.
//   tb_scen_a <image codes> <output file> <off> <passes> U_0 .. U_{K-1} V_0 .. V_{K-1}
#include "../src/scen_a.h"
#include "tb_io.h"

int main(int argc, char** argv) {
    usage_if(argc != 5 + 2 * A_K, "tb_scen_a img.txt out.txt off passes U[K] V[K]");
    const std::vector<long long> img = read_ints(argv[1]);
    const long long off = std::atoll(argv[3]);
    const int passes = std::atoi(argv[4]);
    phase_t U[A_K], V[A_K];
    for (int k = 0; k < A_K; k++) {
        U[k] = phase_t(std::strtoull(argv[5 + k], 0, 10));
        V[k] = phase_t(std::strtoull(argv[5 + A_K + k], 0, 10));
    }
    const int N = A_W * A_H;
    usage_if((int)img.size() != N, "image size differs from A_W x A_H");
    FILE* fo = open_out(argv[2]);
    for (int p = 0; p < passes; p++) {
        hls::stream<pix_t> in, out;
        for (int n = 0; n < N; n++) in.write(pix_t(img[n]));
        scen_a_top(in, out, pix_t(off), U, V, p == 0);
        for (int n = 0; n < N; n++) std::fprintf(fo, "%lld\n", afhls::ll(out.read()));
        if (!in.empty() || !out.empty()) return 1;
    }
    std::fclose(fo);
    return 0;
}
