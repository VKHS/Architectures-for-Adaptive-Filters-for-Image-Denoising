// lms_df: fully parallel direct-form delayed LMS (DLMS), one sample per clock, 2L multipliers.
//
//   F   p_k <- w_k x_k(n)  (+RND on tap 0)          L filter multipliers
//   T   pipelined adder tree, T = ceil(log2 L) register levels
//   E   y, e = sat(d - y), gate, output              error unit
//   U1  q_k <- g(e(n), x_k(n))                       L update multipliers, x delayed T+2 steps
//   U2  A_k <- A_k + q_k
// The loop A -> F -> T -> E -> U1 -> A holds T+4 registers, so the update of sample n is first seen by sample
// n+T+4: adaptation delay D = T + 3 (afarch.engines.adaptation_delay). Every register advances on
// adv = in_valid | in_shift | in_drain, so D counts samples; in_drain pushes bubbles that complete all pending
// updates (row or frame end).
//
// TDL = 0: in_x is the tap vector. TDL = 1: in_x[WD-1:0] is the newest sample of a tapped delay line kept
// inside the engine (x_k(n) = x_0(n-k)); one chain of L+T+1 words then also supplies the delayed taps of
// the update, and in_shift (without in_valid) shifts pre-roll samples into the line.
module lms_df #(
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
    function integer clog2;
        input integer v;
        integer t;
        begin
            clog2 = 0;
            for (t = v - 1; t > 0; t = t >> 1) clog2 = clog2 + 1;
        end
    endfunction
    localparam T  = clog2(L);
    localparam XD = T + 2;                  // steps between the filter and the update of a sample

    assign in_ready = 1'b1;
    wire adv = in_valid | in_shift | in_drain;

    // ------------------------------------------------------------------ taps for the filter and the update
    wire [L*WD-1:0] xf, xu;
    genvar k;
    generate
        if (TDL != 0) begin : g_tdl
            reg signed [WD-1:0] c [0:L+T];             // c[0] = previous newest sample (no reset: SRL)
            wire signed [WD-1:0] newest = in_drain ? {WD{1'b0}} : in_x[WD-1:0];
            integer jt;
            initial for (jt = 0; jt <= L + T; jt = jt + 1) c[jt] = {WD{1'b0}};
            always @(posedge clk)
                if (adv) begin
                    c[0] <= newest;
                    for (jt = 1; jt <= L + T; jt = jt + 1) c[jt] <= c[jt-1];
                end
            assign xf[WD-1:0] = newest;
            for (k = 1; k < L; k = k + 1) begin : g_f
                assign xf[k*WD +: WD] = c[k-1];
            end
            for (k = 0; k < L; k = k + 1) begin : g_u
                assign xu[k*WD +: WD] = c[k + XD - 1];
            end
        end else begin : g_vec
            reg [L*WD-1:0] xp [1:XD];
            integer jv;
            always @(posedge clk)
                if (adv) begin
                    xp[1] <= in_x;
                    for (jv = 2; jv <= XD; jv = jv + 1) xp[jv] <= xp[jv-1];
                end
            assign xf = in_x;
            assign xu = xp[XD];
        end
    endgenerate

    // ------------------------------------------------------------------ filter products and adder tree
    reg signed [WA-1:0] A [0:L-1];
    wire [L*WA-1:0] prods;
    generate
        for (k = 0; k < L; k = k + 1) begin : g_tap
            reg signed [WA-1:0] pq;
            wire signed [WW-1:0] w = view(A[k]);
            wire signed [WD-1:0] x = xf[k*WD +: WD];
            wire signed [WW+WD-1:0] pr = w * x;
            always @(posedge clk) if (adv) pq <= (k == 0) ? (RND + pr) : pr;
            assign prods[k*WA +: WA] = pq;
        end
    endgenerate
    wire signed [WA-1:0] sum;
    adder_tree #(.N(L), .W(WA)) tree (.clk(clk), .en(adv), .in(prods), .out(sum));

    // ------------------------------------------------------------------ sidebands to the error stage
    reg signed [WD-1:0] dq [1:T+1];
    reg signed [WD-1:0] ps [1:T+1];
    reg vq [1:T+1];
    reg aq [1:T+1];
    integer j;
    always @(posedge clk)
        if (rst) for (j = 1; j <= T + 1; j = j + 1) begin vq[j] <= 1'b0; aq[j] <= 1'b0; end
        else if (adv) begin
            dq[1] <= in_d; ps[1] <= in_p; vq[1] <= in_valid; aq[1] <= in_valid & in_adapt;
            for (j = 2; j <= T + 1; j = j + 1) begin
                dq[j] <= dq[j-1]; ps[j] <= ps[j-1]; vq[j] <= vq[j-1]; aq[j] <= aq[j-1];
            end
        end

    // ------------------------------------------------------------------ error unit
    wire signed [WD-1:0] y_c = y_of(sum);
    wire signed [WD-1:0] e_c, o_c;
    wire f_c, a_c;
    wire v_e = vq[T+1];
    lms_err_unit #(.WD(WD), .OUT(OUT), .GATED(GATED), .GKS(GKS), .GRATE(GRATE), .GFRAC(GFRAC),
                   .TMIN(TMIN), .S0(S0)) eu (
        .clk(clk), .rst(rst), .en(adv & v_e), .y(y_c), .d(dq[T+1]), .p(ps[T+1]), .adapt_in(aq[T+1]),
        .e(e_c), .o(o_c), .flag(f_c), .adapt_out(a_c));

    reg signed [WD-1:0] er;
    reg ar_q, qa;
    always @(posedge clk) begin
        out_valid <= !rst & adv & v_e;
        if (rst) begin
            er <= 0; ar_q <= 1'b0; qa <= 1'b0;
            out_o <= 0; out_y <= 0; out_e <= 0; out_flag <= 1'b0;
        end else if (adv) begin
            er <= e_c; ar_q <= v_e & a_c;
            qa <= ar_q;
            if (v_e) begin out_o <= o_c; out_y <= y_c; out_e <= e_c; out_flag <= f_c; end
        end
    end

    // ------------------------------------------------------------------ update: U1 product, U2 accumulate
    generate
        for (k = 0; k < L; k = k + 1) begin : g_upd
            reg signed [WA-1:0] q;
            always @(posedge clk)
                if (rst) A[k] <= A0;
                else if (adv) begin
                    q <= grad(er, xu[k*WD +: WD]);
                    if (qa) A[k] <= upd(A[k], q);
                end
        end
    endgenerate
endmodule
