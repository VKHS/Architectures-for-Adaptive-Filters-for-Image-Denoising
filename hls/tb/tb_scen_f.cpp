// C-simulation testbench of scen_f_top: a sequence of frames (calibration, online, frozen), each row as NOB
// optical-black pixels followed by W scene pixels (and W reference samples with XSEL = 1). Writes one output
// line per scene pixel, every frame.
//   tb_scen_f <frames file> <output file>
// frames file: n_frames, then per frame: mode, then per row: NOB OB codes, W pixel codes [, W reference codes]
#include "../src/scen_f.h"
#include "tb_io.h"

int main(int argc, char** argv) {
    usage_if(argc != 3, "tb_scen_f frames.txt out.txt");
    const std::vector<long long> v = read_ints(argv[1]);
    const int NOB = 1 << F_LOGNOB;
    std::size_t pos = 0;
    const int nf = int(v[pos++]);
    FILE* fo = open_out(argv[2]);
    for (int f = 0; f < nf; f++) {
        const int mode = int(v[pos++]);
        hls::stream<pix_t> in, ref, out;
        for (int i = 0; i < F_H; i++) {
            for (int k = 0; k < NOB; k++) in.write(pix_t(v[pos++]));
            for (int j = 0; j < F_W; j++) in.write(pix_t(v[pos++]));
            if (F_XSEL)
                for (int j = 0; j < F_W; j++) ref.write(pix_t(v[pos++]));
        }
        scen_f_top(in, ref, out, mode, f == 0);
        for (int n = 0; n < F_W * F_H; n++) std::fprintf(fo, "%lld\n", afhls::ll(out.read()));
        if (!in.empty() || !ref.empty() || !out.empty()) return 1;
    }
    std::fclose(fo);
    return pos == v.size() ? 0 : 1;
}
