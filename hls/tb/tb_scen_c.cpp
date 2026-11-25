// C-simulation testbench of scen_c_top: one frame through the canceller. Writes one output pixel per line.
//   tb_scen_c <image codes> <output file>
#include "../src/scen_c.h"
#include "tb_io.h"

int main(int argc, char** argv) {
    usage_if(argc != 3, "tb_scen_c img.txt out.txt");
    const std::vector<long long> img = read_ints(argv[1]);
    const int N = C_W * C_H;
    usage_if((int)img.size() != N, "image size differs from C_W x C_H");
    hls::stream<pix_t> in, out;
    for (int n = 0; n < N; n++) in.write(pix_t(img[n]));
    scen_c_top(in, out, true);
    FILE* fo = open_out(argv[2]);
    for (int n = 0; n < N; n++) std::fprintf(fo, "%lld\n", afhls::ll(out.read()));
    std::fclose(fo);
    return (in.empty() && out.empty()) ? 0 : 1;
}
