// Scenarios D and E: blind-spot predictor (self-tuning filter / line enhancer) on a raster stream.
//
//   pixel -> centre (- off) -> window_gen (2R+1)^2, reflect borders -> taps without the (2*HOLE+1)^2 centre
//         -> engine (any of the six) -> o = y (D, E) or flag ? y : d (gated D) -> + off
//
// Two planes enter the window generator: the tap source and the desired pixel. They are the same stream in
// the first pass; the gated D of the software uses the previous pass's output as tap source in later passes.
// Pipelined engines receive DRAIN_ROW drain steps after every row (the row-block commit needs T + 4) and
// DRAIN_FRAME after the last row, so the model (afarch.scenarios.scenario_de) sees the same step stream.
module scen_de_top #(
    parameter W = 64, HH = 64, R = 2, HOLE = 0,
    parameter ENGINE = 0, P = 2,
    parameter WD = 16, FD = 12, WW = 24, FW = 20, WA = 48, S = 8, RULE = 0, LEAK = 0,
    parameter GATED = 0, GKS = 2, GRATE = 7, GFRAC = 8,
    parameter integer TMIN = 410, S0 = 205,
    parameter [WA-1:0] A0 = 0,
    parameter DRAIN_ROW = 0, DRAIN_FRAME = 64
)(
    input  wire clk, rst,
    input  wire in_valid,
    output wire in_ready,
    input  wire signed [WD-1:0] in_tap, in_d,
    input  wire signed [WD-1:0] off,
    output wire out_valid,
    output wire signed [WD-1:0] out_pix,
    output wire out_flag
);
    localparam K = 2 * R + 1;
    localparam L = K * K - (2 * HOLE + 1) * (2 * HOLE + 1);
    localparam OUT = GATED ? 3 : 1;
    localparam PIPE = (ENGINE >= 2 && ENGINE <= 4);

    // compacted tap index of window position pos (row-major), -1 inside the blind spot
    function integer tap_index;
        input integer pos;
        integer q, n, a, b;
        begin
            n = 0;
            tap_index = -1;
            for (q = 0; q < K * K; q = q + 1) begin
                a = q / K - R;
                b = q % K - R;
                if ((a > HOLE || a < -HOLE) || (b > HOLE || b < -HOLE)) begin
                    if (q == pos) tap_index = n;
                    n = n + 1;
                end
            end
        end
    endfunction

    // ------------------------------------------------------------------ window generator on centred codes
    wire signed [WD-1:0] tap_c = in_tap - off;
    wire signed [WD-1:0] d_c = in_d - off;
    wire w_valid, w_ready, w_last, w_eof;
    wire [K*K*WD-1:0] win;
    wire [2*WD-1:0] ctr;
    window_gen #(.W(W), .HH(HH), .R(R), .WD(WD), .PL(2)) wg (
        .clk(clk), .rst(rst), .in_valid(in_valid), .in_ready(in_ready), .in_pix({d_c, tap_c}),
        .out_valid(w_valid), .out_ready(w_ready), .out_win(win), .out_ctr(ctr), .out_last(w_last),
        .out_eof(w_eof));

    wire [L*WD-1:0] x;
    genvar gp;
    generate
        for (gp = 0; gp < K * K; gp = gp + 1) begin : sel
            if (tap_index(gp) >= 0) begin : tap
                assign x[tap_index(gp)*WD +: WD] = win[gp*WD +: WD];
            end
        end
    endgenerate
    wire signed [WD-1:0] d = ctr[2*WD-1:WD];

    // ------------------------------------------------------------------ drains for the pipelined engines
    reg [15:0] drain_cnt;
    wire draining = (drain_cnt != 0);
    wire e_ready;
    wire e_valid = w_valid && !draining;
    assign w_ready = !draining && e_ready;
    always @(posedge clk)
        if (rst) drain_cnt <= 0;
        else if (e_valid && e_ready && w_last && PIPE) drain_cnt <= w_eof ? DRAIN_FRAME : DRAIN_ROW;
        else if (draining) drain_cnt <= drain_cnt - 1'b1;

    // ------------------------------------------------------------------ engine
    wire eo_valid, eo_flag;
    wire signed [WD-1:0] eo_o, eo_y, eo_e;
    lms_engine #(.ENGINE(ENGINE), .L(L), .P(P), .WD(WD), .FD(FD), .WW(WW), .FW(FW), .WA(WA), .S(S), .RULE(RULE),
                 .LEAK(LEAK), .OUT(OUT), .GATED(GATED), .GKS(GKS), .GRATE(GRATE), .GFRAC(GFRAC), .TMIN(TMIN),
                 .S0(S0), .A0(A0)) eng (
        .clk(clk), .rst(rst), .in_valid(e_valid), .in_shift(1'b0), .in_drain(draining), .in_ready(e_ready),
        .in_x(x), .in_d(d), .in_p(d), .in_adapt(1'b1), .in_last(w_last), .out_valid(eo_valid), .out_o(eo_o),
        .out_y(eo_y), .out_e(eo_e), .out_flag(eo_flag));

    // ------------------------------------------------------------------ restore the offset
    wire signed [WD:0] o_full = eo_o + off;
    assign out_pix = (o_full > $signed({2'b00, {(WD-1){1'b1}}})) ? {1'b0, {(WD-1){1'b1}}} :
                     (o_full < $signed({2'b11, {(WD-1){1'b0}}})) ? {1'b1, {(WD-1){1'b0}}} : o_full[WD-1:0];
    assign out_valid = eo_valid;
    assign out_flag = eo_flag;
endmodule
