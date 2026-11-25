// Scenario A: adaptive notch with synthetic plane-wave references, on a raster stream.
//
// Harmonic k has a 2-D frequency (u_k, v_k); its phase at pixel (i, j) is th = i U_k + j V_k (mod 2^PB), with
// U_k = round(u_k 2^PB) and V_k = round(v_k 2^PB). Two accumulators per harmonic produce it in raster order (the
// row phase steps by U_k per row, the pixel phase by V_k per pixel), so no multiplier is needed. The phase is
// rounded to NA bits and looked up in a 2^NA-entry cosine ROM; sin th = cos(th - pi/2) is a second read of the
// same table, 2^(NA-2) entries back (the second port of the harmonic's block RAM). The 2K references and the
// centred pixel go to the engine, whose error is the output. Model: afarch.scenarios.scenario_a (references:
// afarch.frontends.plane_wave_taps).
module scen_a_top #(
    parameter W = 64, HH = 64, K = 2,
    parameter ENGINE = 0, P = 2,
    parameter WD = 16, FD = 12, WW = 24, FW = 20, WA = 48, S = 16, RULE = 0, LEAK = 0,
    parameter NA = 10, PB = 32,
    parameter [K*PB-1:0] UINC = 0, VINC = 0,        // harmonic 0 in the least significant bits
    parameter COS_FILE = "cos1024_q12.hex",
    parameter DRAIN_ROW = 0, DRAIN_FRAME = 64
)(
    input  wire clk, rst,
    input  wire in_valid,
    output wire in_ready,
    input  wire signed [WD-1:0] in_pix,
    input  wire signed [WD-1:0] off,
    output wire out_valid,
    output wire signed [WD-1:0] out_pix
);
    localparam L = 2 * K;
    localparam PIPE = (ENGINE >= 2 && ENGINE <= 4);
    localparam [PB-1:0] HALF = {{(PB-1){1'b0}}, 1'b1} << (PB - NA - 1);
    localparam [NA-1:0] QUARTER = {{(NA-1){1'b0}}, 1'b1} << (NA - 2);

    // ------------------------------------------------------------------ raster counters and phases
    reg [15:0] col, row;
    reg [PB-1:0] rowph [0:K-1];
    reg [PB-1:0] pixph [0:K-1];
    reg [15:0] drain_cnt;
    wire draining = (drain_cnt != 0);

    // stage 1: the sample waiting for the engine
    reg s1_v, s1_last, s1_eof;
    reg signed [WD-1:0] s1_d;
    wire e_ready;
    wire take = s1_v && e_ready && !draining;
    assign in_ready = !draining && (!s1_v || take);
    wire wr = in_valid && in_ready;

    // ROM reads (synchronous, enabled by an accepted pixel): cos and sin of every harmonic. Each harmonic has its
    // own copy of the table, read through two ports, so it maps onto one dual-port block RAM (RAMB18).
    wire [L*WD-1:0] x;
    genvar g;
    generate
        for (g = 0; g < K; g = g + 1) begin : hk
            wire [PB-1:0] th = pixph[g] + HALF;
            wire [NA-1:0] a = th[PB-1:PB-NA];
            reg [WD-1:0] rom [0:(1<<NA)-1];
            initial $readmemh(COS_FILE, rom);
            reg [WD-1:0] c, s;
            always @(posedge clk) if (wr) begin
                c <= rom[a];
                s <= rom[a - QUARTER];
            end
            assign x[(2*g)*WD +: WD] = c;
            assign x[(2*g+1)*WD +: WD] = s;
        end
    endgenerate

    integer k;
    always @(posedge clk) begin
        if (rst) begin
            col <= 0; row <= 0; s1_v <= 1'b0; s1_last <= 1'b0; s1_eof <= 1'b0; s1_d <= 0; drain_cnt <= 0;
            for (k = 0; k < K; k = k + 1) begin rowph[k] <= 0; pixph[k] <= 0; end
        end else begin
            if (wr) begin
                s1_v <= 1'b1;
                s1_d <= in_pix - off;
                s1_last <= (col == W - 1);
                s1_eof <= (col == W - 1) && (row == HH - 1);
                if (col == W - 1) begin
                    col <= 0;
                    if (row == HH - 1) begin
                        row <= 0;
                        for (k = 0; k < K; k = k + 1) begin rowph[k] <= 0; pixph[k] <= 0; end
                    end else begin
                        row <= row + 1'b1;
                        for (k = 0; k < K; k = k + 1) begin
                            rowph[k] <= rowph[k] + UINC[k*PB +: PB];
                            pixph[k] <= rowph[k] + UINC[k*PB +: PB];
                        end
                    end
                end else begin
                    col <= col + 1'b1;
                    for (k = 0; k < K; k = k + 1) pixph[k] <= pixph[k] + VINC[k*PB +: PB];
                end
            end else if (take) s1_v <= 1'b0;
            if (take && s1_last && PIPE) drain_cnt <= s1_eof ? DRAIN_FRAME : DRAIN_ROW;
            else if (draining) drain_cnt <= drain_cnt - 1'b1;
        end
    end

    // ------------------------------------------------------------------ engine: output = error
    wire eo_valid, eo_flag;
    wire signed [WD-1:0] eo_o, eo_y, eo_e;
    lms_engine #(.ENGINE(ENGINE), .L(L), .P(P), .WD(WD), .FD(FD), .WW(WW), .FW(FW), .WA(WA), .S(S), .RULE(RULE),
                 .LEAK(LEAK), .OUT(0)) eng (
        .clk(clk), .rst(rst), .in_valid(s1_v && !draining), .in_shift(1'b0), .in_drain(draining),
        .in_ready(e_ready), .in_x(x), .in_d(s1_d), .in_p(s1_d), .in_adapt(1'b1), .in_last(s1_last),
        .out_valid(eo_valid), .out_o(eo_o), .out_y(eo_y), .out_e(eo_e), .out_flag(eo_flag));

    wire signed [WD:0] o_full = eo_o + off;
    assign out_pix = (o_full > $signed({2'b00, {(WD-1){1'b1}}})) ? {1'b0, {(WD-1){1'b1}}} :
                     (o_full < $signed({2'b11, {(WD-1){1'b0}}})) ? {1'b1, {(WD-1){1'b0}}} : o_full[WD-1:0];
    assign out_valid = eo_valid;
endmodule
