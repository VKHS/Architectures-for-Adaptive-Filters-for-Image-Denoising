// lms_systolic: systolic delayed LMS, one sample per clock, 2L multipliers, only local connections.
//
// Tap j sees its input x_j(m) skewed by j steps and adds its product to a partial sum that moves one tap per
// step (the DSP48 PCOUT->PCIN cascade):
//     P_j <- w_j * xs_j            xs_j(t) = x_j(t - j)
//     S_j <- S_(j-1) + P_j         S_(-1) = RND
// so S_(L-1) delivers y(m) = sum_j w_j(m + j) x_j(m) at step m + L + 1. The error then walks down an error
// chain, one register per tap, and tap j updates with e(m) at step m + L + 2 + j. In the skewed weights
// w^_j(m) = w_j(m + j) this is an ordinary DLMS with the SAME delay for every tap: D = L + 3.
//
// TDL = 0: in_x is the tap vector; tap j keeps a private line of L + 2 + j words (skew + update alignment).
// TDL = 1: in_x[WD-1:0] is the newest sample of a tapped delay line; then x_j(m - j) = x_0(m - 2j) and one shared
//          chain of 3L + 1 words supplies every tap: the classic systolic FIR with two registers per tap.
// Every register advances on adv = in_valid | in_shift | in_drain.
module lms_systolic #(
    parameter L = 8, TDL = 0,
    parameter WD = 16, FD = 12, WW = 24, FW = 20, WA = 48, S = 7, RULE = 0, LEAK = 0,
    parameter OUT = 0, GATED = 0, GKS = 2, GRATE = 7, GFRAC = 8,
    parameter integer TMIN = 410, S0 = 205,
    parameter [WA-1:0] A0 = 0
)(
    input  wire clk, rst,
    input  wire in_valid, in_shift, in_drain,
    output wire in_ready,
    input  wire [L*WD-1:0] in_x,
    input  wire signed [WD-1:0] in_d, in_p,
    input  wire in_adapt,
    output reg  out_valid,
    output reg  signed [WD-1:0] out_o, out_y, out_e,
    output reg  out_flag
);
    `include "lms_arith.vh"
    localparam UD = L + 2;                       // extra steps from the filter to the update of a tap

    assign in_ready = 1'b1;
    wire adv = in_valid | in_shift | in_drain;

    // ------------------------------------------------------------------ skewed taps: xs_j (filter), xu_j (update)
    wire [L*WD-1:0] xs, xu;
    genvar k;
    integer js, je;
    generate
        if (TDL != 0) begin : g_tdl
            localparam NC = 2*(L-1) + UD + 1;
            reg signed [WD-1:0] c [0:NC-1];          // c[i] = x_0(t - 1 - i)
            wire signed [WD-1:0] newest = in_drain ? {WD{1'b0}} : in_x[WD-1:0];
            integer jt;
            initial for (jt = 0; jt < NC; jt = jt + 1) c[jt] = {WD{1'b0}};
            always @(posedge clk)
                if (adv) begin
                    c[0] <= newest;
                    for (jt = 1; jt < NC; jt = jt + 1) c[jt] <= c[jt-1];
                end
            assign xs[WD-1:0] = newest;
            for (k = 1; k < L; k = k + 1) begin : g_s
                assign xs[k*WD +: WD] = c[2*k - 1];
            end
            for (k = 0; k < L; k = k + 1) begin : g_u
                assign xu[k*WD +: WD] = c[2*k + UD - 1];
            end
        end else begin : g_vec
            for (k = 0; k < L; k = k + 1) begin : g_line
                reg signed [WD-1:0] ln [0:k+UD-1];       // ln[i] = x_k(t - 1 - i)
                integer i;
                initial for (i = 0; i < k + UD; i = i + 1) ln[i] = {WD{1'b0}};
                always @(posedge clk)
                    if (adv) begin
                        ln[0] <= in_x[k*WD +: WD];
                        for (i = 1; i < k + UD; i = i + 1) ln[i] <= ln[i-1];
                    end
                if (k == 0) begin : g_s0
                    assign xs[WD-1:0] = in_x[WD-1:0];
                end else begin : g_sk
                    assign xs[k*WD +: WD] = ln[k-1];
                end
                assign xu[k*WD +: WD] = ln[k + UD - 1];
            end
        end
    endgenerate

    // ------------------------------------------------------------------ systolic sum chain
    reg signed [WA-1:0] A [0:L-1];
    wire [L*WA-1:0] schain;
    generate
        for (k = 0; k < L; k = k + 1) begin : g_cell
            reg signed [WA-1:0] P, Sj;
            wire signed [WW-1:0] w = view(A[k]);
            wire signed [WD-1:0] x = xs[k*WD +: WD];
            wire signed [WW+WD-1:0] pr = w * x;
            wire signed [WA-1:0] s_in;
            if (k == 0) begin : g_head
                assign s_in = RND;
            end else begin : g_link
                assign s_in = schain[(k-1)*WA +: WA];
            end
            always @(posedge clk)
                if (adv) begin
                    P <= pr;
                    Sj <= s_in + P;
                end
            assign schain[k*WA +: WA] = Sj;
        end
    endgenerate
    wire signed [WA-1:0] sum = schain[(L-1)*WA +: WA];

    // ------------------------------------------------------------------ sidebands: L + 1 steps to the error stage
    reg signed [WD-1:0] dq [1:L+1];
    reg signed [WD-1:0] ps [1:L+1];
    reg vq [1:L+1];
    reg aq [1:L+1];
    always @(posedge clk)
        if (rst) for (js = 1; js <= L + 1; js = js + 1) begin vq[js] <= 1'b0; aq[js] <= 1'b0; end
        else if (adv) begin
            dq[1] <= in_d; ps[1] <= in_p; vq[1] <= in_valid; aq[1] <= in_valid & in_adapt;
            for (js = 2; js <= L + 1; js = js + 1) begin
                dq[js] <= dq[js-1]; ps[js] <= ps[js-1]; vq[js] <= vq[js-1]; aq[js] <= aq[js-1];
            end
        end

    wire signed [WD-1:0] y_c = y_of(sum);
    wire signed [WD-1:0] e_c, o_c;
    wire f_c, a_c;
    wire v_e = vq[L+1];
    lms_err_unit #(.WD(WD), .OUT(OUT), .GATED(GATED), .GKS(GKS), .GRATE(GRATE), .GFRAC(GFRAC),
                   .TMIN(TMIN), .S0(S0)) eu (
        .clk(clk), .rst(rst), .en(adv & v_e), .y(y_c), .d(dq[L+1]), .p(ps[L+1]), .adapt_in(aq[L+1]),
        .e(e_c), .o(o_c), .flag(f_c), .adapt_out(a_c));

    // ------------------------------------------------------------------ error chain and local updates
    reg signed [WD-1:0] ec [0:L-1];
    reg ea [0:L-1];
    always @(posedge clk) begin
        out_valid <= !rst & adv & v_e;
        if (rst) begin
            for (je = 0; je < L; je = je + 1) begin ec[je] <= 0; ea[je] <= 1'b0; end
            out_o <= 0; out_y <= 0; out_e <= 0; out_flag <= 1'b0;
        end else if (adv) begin
            ec[0] <= e_c; ea[0] <= v_e & a_c;
            for (je = 1; je < L; je = je + 1) begin ec[je] <= ec[je-1]; ea[je] <= ea[je-1]; end
            if (v_e) begin out_o <= o_c; out_y <= y_c; out_e <= e_c; out_flag <= f_c; end
        end
    end
    generate
        for (k = 0; k < L; k = k + 1) begin : g_upd
            reg signed [WA-1:0] q;
            reg qa;
            always @(posedge clk)
                if (rst) begin A[k] <= A0; qa <= 1'b0; end
                else if (adv) begin
                    q  <= grad(ec[k], xu[k*WD +: WD]);
                    qa <= ea[k];
                    if (qa) A[k] <= upd(A[k], q);
                end
        end
    endgenerate
endmodule
