// C-simulation testbench of scen_b_top: one frame through the bias canceller. Writes "e b" per pixel.
//   tb_scen_b <image codes> <output file>
#include "../src/scen_b.h"
#include "tb_io.h"

int main(int argc, char** argv) {
    usage_if(argc != 3, "tb_scen_b img.txt out.txt");
    const std::vector<long long> img = read_ints(argv[1]);
    const int N = B_W * B_H;
    usage_if((int)img.size() != N, "image size differs from B_W x B_H");
    hls::stream<pix_t> in, out, bias;
    for (int n = 0; n < N; n++) in.write(pix_t(img[n]));
    scen_b_top(in, out, bias);
    FILE* fo = open_out(argv[2]);
    for (int n = 0; n < N; n++) {
        const long long e = afhls::ll(out.read());
        std::fprintf(fo, "%lld %lld\n", e, afhls::ll(bias.read()));
    }
    std::fclose(fo);
    return 0;
}
