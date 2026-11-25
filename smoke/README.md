# smoke/: every scenario through the RTL and the HLS C++

[Repository](../README.md) · [HLS](../hls/README.md) · [RTL](../rtl/README.md) · [verification](../docs/05-verification.md#53-smoke-tests-every-scenario-rtl-and-hls)

The short test of the whole stack. Each case is a small corrupted crop (a few hundred pixels) with one
configuration of one scenario. The golden output comes from the bit-accurate models of [`afarch`](../afarch/README.md);
the Verilog top runs in Icarus Verilog through its testbench in [`tb/`](../tb/README.md), with 10 % random idle cycles
between pixels; the HLS C++ top is compiled with g++ as a C simulation ([`hls/tb`](../hls/tb)). Both must reproduce
the golden output **word for word**: the pixels, and the gate flags of D or the bias track of B.

```bash
python smoke/smoke.py                        # all 17 cases, RTL and HLS (about 2 minutes)
python smoke/smoke.py A D                    # some scenarios
python smoke/smoke.py --only rtl             # one implementation
python smoke/smoke.py --only hls --ap-types <dir>   # the HLS with exact-width ap_int types
python smoke/smoke.py --list C               # the case names
```

```
case                   pixels  RTL    HLS     configuration
A_serial                  768  PASS   PASS    2 plane waves, L = 4, 2 passes
A_df                      768  PASS   PASS    2 plane waves, L = 4, 2 passes
B_lms                     768  PASS   PASS    lms update, S = 6
B_sign                    768  PASS   PASS    sign update, S = 6
B_gated                   768  PASS   PASS    gated update, S = 4
C_folded                  384  PASS   PASS    L = 16, delay 6
C_df                      384  PASS   PASS    L = 16, delay 6
C_rowblock                384  PASS   PASS    L = 16, delay 6
D_gated_serial            768  PASS   PASS    5 x 5 window, blind spot 1 x 1, L = 24, gated, 3 passes
D_gated_df                768  PASS   PASS    5 x 5 window, blind spot 1 x 1, L = 24, gated, 3 passes
D_systolic                768  PASS   PASS    5 x 5 window, blind spot 1 x 1, L = 24, 2 passes
E_systolic                768  PASS   PASS    7 x 7 window, blind spot 3 x 3, L = 40, 2 passes
E_rowblock                768  PASS   PASS    7 x 7 window, blind spot 3 x 3, L = 40, 2 passes
E_da                      768  PASS   PASS    7 x 7 window, blind spot 1 x 1, L = 48, 2 passes
F_ob_cal                 1200  PASS   PASS    OB reference, 2 dark frames then a frozen frame, S = 1
F_online                  400  PASS   PASS    OB reference, online (mode 2), S = -3
F_channel                 800  PASS   PASS    reference channel, dark frame then frozen, S = -1
ALL PASS
```

## The cases

| scenario | case | scene | configuration | what it exercises |
|---|---|---|---|---|
| [A](../docs/scenarios/A.md#6-smoke-test) | `A_serial`, `A_df` | coffee, 32 x 24, two plane waves $(0.031,0)$ and $(0.012,0.137)$ | $K=2$, $\mu=2^{-10}$, two passes | phase accumulators across rows and passes, the cosine ROM, exact and delayed classes |
| [B](../docs/scenarios/B.md#6-smoke-test) | `B_lms`, `B_sign`, `B_gated` | a synthetic scan, 48 x 16, offsets and a ramp | the three update modes | the multiplier-free loop, row starts, the bias track |
| [C](../docs/scenarios/C.md#6-smoke-test) | `C_folded`, `C_df`, `C_rowblock` | chelsea, 64 x 6, oblique stripes, signed codes | $L=16$, $\Delta=6$, $\mu=2^{-6}$ | the high band, the reflected history, pre-roll, the three classes |
| [D](../docs/scenarios/D.md#6-smoke-test) | `D_gated_serial`, `D_gated_df`, `D_systolic` | gravel with 12 % impulses; cameraman with Gaussian noise; 32 x 24 | $5\times5$, gated over three passes, plain | the window with reflected borders, the gate, the tap plane from the previous pass |
| [E](../docs/scenarios/E.md#6-smoke-test) | `E_systolic`, `E_rowblock`, `E_da` | cameraman with Gaussian noise, 32 x 24 | $7\times7$, blind spots $3\times3$ and $1\times1$ | larger windows, the blind spot, the multiplier-free block engine |
| [F](../docs/scenarios/F.md#6-smoke-test) | `F_ob_cal`, `F_online`, `F_channel` | hubble, 40 x 10, banding, telegraph, 16 OB columns | frame sequences, $S=1$, $-3$, $-1$ | modes 0, 1 and 2, the leave-one-out reference, the reference channel, negative steps |

A full run (both implementations, all scenarios) writes [`results/smoke.json`](../results/smoke.json). The continuous
integration ([`.github/workflows/ci.yml`](../.github/workflows/ci.yml)) runs the test on every push, once with
64-bit integers and once with `ap_int`, using the open
[HLS arbitrary-precision headers](https://github.com/Xilinx/HLS_arbitrary_Precision_Types) fetched at test time.

## With Vitis HLS

Every case leaves `build/smoke/<case>/vitis_case.tcl`, its configuration for
[`hls/scripts/run_vitis_hls.tcl`](../hls/scripts/run_vitis_hls.tcl). [`run_vitis.sh`](run_vitis.sh) runs the C
simulation with the `ap_int` headers of the installed Vitis, then every case through Vitis HLS (C simulation,
synthesis, C/RTL co-simulation), then compares the words the co-simulation wrote with the model:

```bash
source <Vitis installation>/settings64.sh
bash smoke/run_vitis.sh                      # every scenario
bash smoke/run_vitis.sh D E                  # some
FLOW=syn bash smoke/run_vitis.sh C           # stop after synthesis (csim | syn | cosim | export)
PART=xczu7ev-ffvc1156-2-e PERIOD=3.0 bash smoke/run_vitis.sh D
python smoke/smoke.py --vitis D              # the comparison alone
```

The synthesis reports go to `build/vitis_hls/<case>/sol/syn/report/`.
