// C-simulation testbench of scen_de_top: streams an image PASSES times; in the gated mode the taps of a later
// pass come from the previous pass's output, as in the software and in tb/tb_scen_de.v. Writes "pix flag" per
// output pixel, every pass.
//   tb_scen_de <image codes> <output file> <off> <a0 weight in Q20> <passes>
#include "../src/scen_de.h"
#include "tb_io.h"

int main(int argc, char** argv) {
    usage_if(argc != 6, "tb_scen_de img.txt out.txt off a0_wq passes");
    const std::vector<long long> img = read_ints(argv[1]);
    const long long off = std::atoll(argv[3]), a0 = std::atoll(argv[4]);
    const int passes = std::atoi(argv[5]);
    const int N = DE_W * DE_H;
    usage_if((int)img.size() != N, "image size differs from DE_W x DE_H");
    FILE* fo = open_out(argv[2]);
    std::vector<long long> prev(img);
    for (int p = 0; p < passes; p++) {
        hls::stream<pix_t> tap_in, d_in, pix_out;
        hls::stream<bool> flag_out;
        for (int n = 0; n < N; n++) {
            tap_in.write(pix_t((DE_GATED && p > 0) ? prev[n] : img[n]));
            d_in.write(pix_t(img[n]));
        }
        scen_de_top(tap_in, d_in, pix_out, flag_out, pix_t(off), a0, p == 0);
        for (int n = 0; n < N; n++) {
            const long long v = afhls::ll(pix_out.read());
            const bool f = flag_out.read();
            prev[n] = v;
            std::fprintf(fo, "%lld %d\n", v, f ? 1 : 0);
        }
        if (!tap_in.empty() || !d_in.empty() || !pix_out.empty()) {
            std::fprintf(stderr, "tb_scen_de: streams not balanced after pass %d\n", p);
            return 1;
        }
    }
    std::fclose(fo);
    return 0;
}
