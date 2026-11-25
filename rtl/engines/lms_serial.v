// lms_serial: exact LMS on ONE shared multiplier (one DSP slice).
//
// Per sample: accept -> L filter cycles (acc += w_k x_k) -> 1 drain -> error -> L update cycles
// (A_k += e x_k) -> accept. The multiplier operand A is the weight view during filtering and the error during
// the update; the accumulators A_k live in a single-port-write memory (LUTRAM), cleared after reset in L cycles.
// Initiation interval: 2L + 3 cycles with adaptation, L + 3 without (adapt = 0 or a gated sample).
module lms_serial #(
    parameter L = 4,
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
            clog2 = 1;
            for (t = v - 1; t > 1; t = t >> 1) clog2 = clog2 + 1;
        end
    endfunction
    localparam IW = clog2(L + 1);
    localparam [2:0] CLR = 3'd0, IDLE = 3'd1, FILT = 3'd2, FDRN = 3'd3, ERR = 3'd4, UPD = 3'd5;

    reg [2:0] state;
    reg [IW-1:0] idx, qidx;
    reg signed [WA-1:0] A [0:L-1];
    reg signed [WD-1:0] xr [0:L-1];
    reg signed [WD-1:0] dr, pr, er;
    reg ar;
    reg signed [WA-1:0] acc, gq;
    reg pv, qv;
    integer i;

    // the one multiplier: (weight view | error) x tap
    wire signed [WW-1:0] wv = view(A[idx]);
    wire signed [WW-1:0] mul_a = (state == UPD) ? {{(WW-WD){er[WD-1]}}, er} : wv;
    wire signed [WD-1:0] mul_b = xr[idx];
    wire signed [WW+WD-1:0] prod = mul_a * mul_b;
    reg  signed [WW+WD-1:0] prod_q;

    // accumulator memory: one write port (clear or update write-back), reads at idx (filter) and at the write
    // address (read-modify-write), so it maps to distributed RAM
    wire          a_we    = (state == CLR) | qv;
    wire [IW-1:0] a_waddr = (state == CLR) ? idx : qidx;
    wire signed [WA-1:0] a_wdata = (state == CLR) ? $signed(A0) : upd(A[a_waddr], gq);
    always @(posedge clk) if (a_we) A[a_waddr] <= a_wdata;

    // error unit, evaluated in state ERR
    wire signed [WD-1:0] y_c = y_of(acc);
    wire signed [WD-1:0] e_c, o_c;
    wire f_c, a_c;
    lms_err_unit #(.WD(WD), .OUT(OUT), .GATED(GATED), .GKS(GKS), .GRATE(GRATE), .GFRAC(GFRAC),
                   .TMIN(TMIN), .S0(S0)) eu (
        .clk(clk), .rst(rst), .en(state == ERR), .y(y_c), .d(dr), .p(pr), .adapt_in(ar),
        .e(e_c), .o(o_c), .flag(f_c), .adapt_out(a_c));

    assign in_ready = (state == IDLE);

    always @(posedge clk) begin
        out_valid <= 1'b0;
        if (rst) begin
            state <= CLR; idx <= 0; qidx <= 0; pv <= 1'b0; qv <= 1'b0; acc <= 0; gq <= 0;
            dr <= 0; pr <= 0; er <= 0; ar <= 1'b0; prod_q <= 0;
            out_o <= 0; out_y <= 0; out_e <= 0; out_flag <= 1'b0;
        end else begin
            qv <= 1'b0;                 // the write-back (a_we) is one cycle behind the update multiplier
            case (state)
                CLR: begin
                    if (idx == L - 1) begin idx <= 0; state <= IDLE; end
                    else idx <= idx + 1'b1;
                end
                IDLE: if (in_valid) begin
                    for (i = 0; i < L; i = i + 1) xr[i] <= in_x[i*WD +: WD];
                    dr <= in_d; pr <= in_p; ar <= in_adapt;
                    acc <= RND; idx <= 0; pv <= 1'b0;
                    state <= FILT;
                end
                FILT: begin
                    prod_q <= prod;
                    pv <= 1'b1;
                    if (pv) acc <= acc + prod_q;
                    if (idx == L - 1) state <= FDRN;
                    else idx <= idx + 1'b1;
                end
                FDRN: begin
                    acc <= acc + prod_q;
                    pv <= 1'b0;
                    state <= ERR;
                end
                ERR: begin
                    out_valid <= 1'b1;
                    out_o <= o_c; out_y <= y_c; out_e <= e_c; out_flag <= f_c;
                    er <= e_c;
                    idx <= 0;
                    state <= a_c ? UPD : IDLE;
                end
                UPD: begin
                    gq <= (RULE == 0) ? prod : grad(er, xr[idx]);
                    qidx <= idx;
                    qv <= 1'b1;
                    if (idx == L - 1) state <= IDLE;
                    else idx <= idx + 1'b1;
                end
                default: state <= IDLE;
            endcase
        end
    end
endmodule
