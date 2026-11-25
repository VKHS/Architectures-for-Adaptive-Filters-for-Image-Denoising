// lms_engine: one port list for the six engine architectures; ENGINE selects the implementation.
//
//   ENGINE 0 lms_serial    exact LMS, 1 multiplier, II = 2L + 3
//          1 lms_folded    exact LMS, P lanes x 2 multipliers, II = ceil(L/P) + ceil(log2 P) + 5
//          2 lms_df        delayed LMS, 2L multipliers, II = 1, D = ceil(log2 L) + 3
//          3 lms_systolic  delayed LMS, 2L multipliers, II = 1, D = L + 3, local connections only
//          4 lms_rowblock  block LMS (block = row), 2L multipliers, II = 1
//          5 lms_da        block LMS, no multiplier (distributed arithmetic), II = WD + ceil(log2 ceil(L/4)) + 3
// Handshake engines (0, 1, 5) use in_ready; pipelined engines (2, 3, 4) take a sample every cycle and use
// in_shift (TDL pre-roll) and in_drain. in_last marks the end of a block (4, 5).
module lms_engine #(
    parameter ENGINE = 0, L = 4, P = 2, TDL = 0,
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
    input  wire in_adapt, in_last,
    output wire out_valid,
    output wire signed [WD-1:0] out_o, out_y, out_e,
    output wire out_flag
);
    generate
        if (ENGINE == 0) begin : u
            lms_serial #(.L(L), .WD(WD), .FD(FD), .WW(WW), .FW(FW), .WA(WA), .S(S), .RULE(RULE), .LEAK(LEAK),
                         .OUT(OUT), .GATED(GATED), .GKS(GKS), .GRATE(GRATE), .GFRAC(GFRAC), .TMIN(TMIN),
                         .S0(S0), .A0(A0)) e (
                .clk(clk), .rst(rst), .in_valid(in_valid), .in_ready(in_ready), .in_x(in_x), .in_d(in_d),
                .in_p(in_p), .in_adapt(in_adapt), .out_valid(out_valid), .out_o(out_o), .out_y(out_y),
                .out_e(out_e), .out_flag(out_flag));
        end else if (ENGINE == 1) begin : u
            lms_folded #(.L(L), .P(P), .WD(WD), .FD(FD), .WW(WW), .FW(FW), .WA(WA), .S(S), .RULE(RULE),
                         .LEAK(LEAK), .OUT(OUT), .GATED(GATED), .GKS(GKS), .GRATE(GRATE), .GFRAC(GFRAC),
                         .TMIN(TMIN), .S0(S0), .A0(A0)) e (
                .clk(clk), .rst(rst), .in_valid(in_valid), .in_ready(in_ready), .in_x(in_x), .in_d(in_d),
                .in_p(in_p), .in_adapt(in_adapt), .out_valid(out_valid), .out_o(out_o), .out_y(out_y),
                .out_e(out_e), .out_flag(out_flag));
        end else if (ENGINE == 2) begin : u
            lms_df #(.L(L), .TDL(TDL), .WD(WD), .FD(FD), .WW(WW), .FW(FW), .WA(WA), .S(S), .RULE(RULE),
                     .LEAK(LEAK), .OUT(OUT), .GATED(GATED), .GKS(GKS), .GRATE(GRATE), .GFRAC(GFRAC), .TMIN(TMIN),
                     .S0(S0), .A0(A0)) e (
                .clk(clk), .rst(rst), .in_valid(in_valid), .in_shift(in_shift), .in_drain(in_drain),
                .in_ready(in_ready), .in_x(in_x), .in_d(in_d), .in_p(in_p), .in_adapt(in_adapt),
                .out_valid(out_valid), .out_o(out_o), .out_y(out_y), .out_e(out_e), .out_flag(out_flag));
        end else if (ENGINE == 3) begin : u
            lms_systolic #(.L(L), .TDL(TDL), .WD(WD), .FD(FD), .WW(WW), .FW(FW), .WA(WA), .S(S), .RULE(RULE),
                           .LEAK(LEAK), .OUT(OUT), .GATED(GATED), .GKS(GKS), .GRATE(GRATE), .GFRAC(GFRAC),
                           .TMIN(TMIN), .S0(S0), .A0(A0)) e (
                .clk(clk), .rst(rst), .in_valid(in_valid), .in_shift(in_shift), .in_drain(in_drain),
                .in_ready(in_ready), .in_x(in_x), .in_d(in_d), .in_p(in_p), .in_adapt(in_adapt),
                .out_valid(out_valid), .out_o(out_o), .out_y(out_y), .out_e(out_e), .out_flag(out_flag));
        end else if (ENGINE == 4) begin : u
            lms_rowblock #(.L(L), .TDL(TDL), .WD(WD), .FD(FD), .WW(WW), .FW(FW), .WA(WA), .S(S), .RULE(RULE),
                           .LEAK(LEAK), .OUT(OUT), .GATED(GATED), .GKS(GKS), .GRATE(GRATE), .GFRAC(GFRAC),
                           .TMIN(TMIN), .S0(S0), .A0(A0)) e (
                .clk(clk), .rst(rst), .in_valid(in_valid), .in_shift(in_shift), .in_drain(in_drain),
                .in_ready(in_ready), .in_x(in_x), .in_d(in_d), .in_p(in_p), .in_adapt(in_adapt),
                .in_last(in_last), .out_valid(out_valid), .out_o(out_o), .out_y(out_y), .out_e(out_e),
                .out_flag(out_flag));
        end else begin : u
            lms_da #(.L(L), .RULE(RULE), .WD(WD), .FD(FD), .WW(WW), .FW(FW), .WA(WA), .S(S), .LEAK(LEAK),
                     .OUT(OUT), .GATED(GATED), .GKS(GKS), .GRATE(GRATE), .GFRAC(GFRAC), .TMIN(TMIN), .S0(S0),
                     .A0(A0)) e (
                .clk(clk), .rst(rst), .in_valid(in_valid), .in_ready(in_ready), .in_x(in_x), .in_d(in_d),
                .in_p(in_p), .in_adapt(in_adapt), .in_last(in_last), .out_valid(out_valid), .out_o(out_o),
                .out_y(out_y), .out_e(out_e), .out_flag(out_flag));
        end
    endgenerate
endmodule
