// lms_folded: exact LMS on P lanes with two multipliers each (2P DSP slices), one fused pass per sample.
//
// Tap k = m*P + p belongs to lane p, word m (M = ceil(L/P) words per lane). In the pass of sample n every
// lane walks its M words and, for each tap,
//     S1  q   <- g(e(n-1), x_k(n-1))            update product of the PREVIOUS sample (if it adapted)
//     S2  A_k <- A_k + q;  w <- view(A_k)       read-modify-write of the lane's accumulator bank
//     S3  r   <- w * x_k(n)                     filter product with the freshly updated weight
//     S4  lane accumulator += r
// so the weights used for y(n) contain every update up to n-1: exact LMS, with half the passes of lms_serial.
// The P lane sums meet in a pipelined adder tree (T = ceil(log2 P) levels); RND is preloaded in lane 0.
// Initiation interval: M + T + 5 cycles (measured: tb/tb_engine.v).
module lms_folded #(
    parameter L = 8, P = 2,
    parameter WD = 16, FD = 12, WW = 24, FW = 20, WA = 48, S = 7, RULE = 0, LEAK = 0,
    parameter OUT = 0, GATED = 0, GKS = 2, GRATE = 7, GFRAC = 8,
    parameter integer TMIN = 410, S0 = 205,
    parameter [WA-1:0] A0 = 0
)(
    input  wire clk, rst,
    input  wire in_valid,
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
    localparam M  = (L + P - 1) / P;
    localparam T  = clog2(P);
    localparam MW = (clog2(M + 1) > 0) ? clog2(M + 1) : 1;
    localparam DEPTH = T + 4;          // cycles from the last S1 issue to the sum at the tree output

    localparam [1:0] CLR = 2'd0, IDLE = 2'd1, PASS = 2'd2, TAIL = 2'd3;
    reg [1:0] state;
    reg [MW-1:0] m;                    // word being issued (S1)
    reg [7:0] tail;                    // cycles spent waiting for the tree
    reg signed [WD-1:0] e_prev, dr, pr;
    reg pend, ar;
    integer i;

    // pipeline control bits that travel with the issued word
    reg       v1, v2, v3;              // S1, S2, S3 hold a valid word
    reg       f1, f2, f3;              // first word of the pass
    reg [MW-1:0] m1;

    wire [P*WA-1:0] lane_sum;
    wire [M*P*WD-1:0] xpad;            // taps padded with zeros to M*P
    generate
        if (M*P > L) begin : g_pad
            assign xpad = {{((M*P-L)*WD){1'b0}}, in_x};
        end else begin : g_nopad
            assign xpad = in_x;
        end
    endgenerate

    genvar gp;
    generate
        for (gp = 0; gp < P; gp = gp + 1) begin : lane
            reg signed [WA-1:0] Ab [0:M-1];           // accumulator bank of this lane
            reg signed [WD-1:0] xc [0:M-1];           // taps of sample n
            reg signed [WD-1:0] xp [0:M-1];           // taps of sample n-1
            reg signed [WA-1:0] q;                    // S1 -> S2
            reg signed [WW-1:0] w2;                   // S2 -> S3
            reg signed [WD-1:0] x2;
            reg signed [WW+WD-1:0] r;                 // S3 -> S4
            reg signed [WA-1:0] lacc;                 // S4 lane accumulator
            // one write port: clear (CLR) or the S2 read-modify-write; distributed RAM
            wire          a_we    = (state == CLR) | (v1 & pend);
            wire [MW-1:0] a_addr  = (state == CLR) ? m : m1;
            wire signed [WA-1:0] a_new = (pend) ? upd(Ab[a_addr], q) : Ab[a_addr];
            always @(posedge clk) if (a_we) Ab[a_addr] <= (state == CLR) ? $signed(A0) : a_new;
            integer k;
            always @(posedge clk) begin
                if (state == IDLE && in_valid)
                    for (k = 0; k < M; k = k + 1) begin
                        xp[k] <= xc[k];
                        xc[k] <= xpad[(k*P + gp)*WD +: WD];
                    end
                // S1
                if (state == PASS) q <= grad(e_prev, xp[m]);
                // S2
                if (v1) begin
                    w2 <= view(a_new);
                    x2 <= xc[m1];
                end
                // S3
                if (v2) r <= w2 * x2;
                // S4
                if (v3) lacc <= (f3 ? ((gp == 0) ? RND : 0) : lacc) + r;   // keep every operand signed
            end
            assign lane_sum[gp*WA +: WA] = lacc;
        end
    endgenerate

    wire signed [WA-1:0] sum;
    adder_tree #(.N(P), .W(WA)) tree (.clk(clk), .en(1'b1), .in(lane_sum), .out(sum));

    wire signed [WD-1:0] y_c = y_of(sum);
    wire signed [WD-1:0] e_c, o_c;
    wire f_c, a_c;
    wire at_err = (state == TAIL) && (tail == DEPTH - 1);
    lms_err_unit #(.WD(WD), .OUT(OUT), .GATED(GATED), .GKS(GKS), .GRATE(GRATE), .GFRAC(GFRAC),
                   .TMIN(TMIN), .S0(S0)) eu (
        .clk(clk), .rst(rst), .en(at_err), .y(y_c), .d(dr), .p(pr), .adapt_in(ar),
        .e(e_c), .o(o_c), .flag(f_c), .adapt_out(a_c));

    assign in_ready = (state == IDLE);

    always @(posedge clk) begin
        out_valid <= 1'b0;
        if (rst) begin
            state <= CLR; m <= 0; tail <= 0; pend <= 1'b0; e_prev <= 0; dr <= 0; pr <= 0; ar <= 1'b0;
            v1 <= 1'b0; v2 <= 1'b0; v3 <= 1'b0; f1 <= 1'b0; f2 <= 1'b0; f3 <= 1'b0; m1 <= 0;
            out_o <= 0; out_y <= 0; out_e <= 0; out_flag <= 1'b0;
        end else begin
            v1 <= (state == PASS); f1 <= (state == PASS) && (m == 0); m1 <= m;
            v2 <= v1; f2 <= f1;
            v3 <= v2; f3 <= f2;
            case (state)
                CLR: if (m == M - 1) begin m <= 0; state <= IDLE; end else m <= m + 1'b1;
                IDLE: if (in_valid) begin
                    dr <= in_d; pr <= in_p; ar <= in_adapt;
                    m <= 0;
                    state <= PASS;
                end
                PASS: if (m == M - 1) begin tail <= 0; state <= TAIL; end else m <= m + 1'b1;
                TAIL: if (tail == DEPTH - 1) begin
                    out_valid <= 1'b1;
                    out_o <= o_c; out_y <= y_c; out_e <= e_c; out_flag <= f_c;
                    e_prev <= e_c;
                    pend <= a_c;
                    state <= IDLE;
                end else tail <= tail + 1'b1;
            endcase
        end
    end
endmodule
