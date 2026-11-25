// Scenario B: bias (drift) canceller along every row. The adaptive filter has one weight and the constant
// reference x = 1, so the multiplier disappears: the weight is the bias b itself.
//
//   Bacc  : FD + S fractional bits;  b = sat(Bacc >>> S);  e = sat(d - b) is the output
//   MODE 0 LMS   : Bacc += e                (b += 2^-S e)
//   MODE 1 sign  : Bacc += sgn(e) << SK     (b moves by 2^(SK-S) LSB per pixel; tracks the median)
//   MODE 2 gated : Bacc += e if |e| < TAU   (adapts on the background only)
// The first pixel of every row loads b = d. The loop Bacc -> b -> e -> Bacc holds one register, a subtractor
// and an adder: one sample per clock without any pipelining. Model: afarch.scenarios.bias_run.
module scen_b_top #(
    parameter W = 64, WD = 16, S = 6, MODE = 0, SK = 0,
    parameter integer TAU = 328
)(
    input  wire clk, rst,
    input  wire in_valid,
    output wire in_ready,
    input  wire signed [WD-1:0] in_pix,
    output reg  out_valid,
    output reg  signed [WD-1:0] out_pix, out_bias
);
    localparam WB = WD + S + 2;
    localparam signed [WB-1:0] BMAX = (1 <<< (WD - 1)) - 1;
    localparam signed [WB-1:0] BMIN = -(1 <<< (WD - 1));
    assign in_ready = 1'b1;

    reg [15:0] col;
    reg signed [WB-1:0] Bacc;
    wire first = (col == 0);
    wire signed [WB-1:0] d_w = in_pix;
    wire signed [WB-1:0] bacc_eff = first ? (d_w <<< S) : Bacc;
    wire signed [WB-1:0] bsh = bacc_eff >>> S;
    wire signed [WD-1:0] b = (bsh > BMAX) ? BMAX[WD-1:0] : (bsh < BMIN) ? BMIN[WD-1:0] : bsh[WD-1:0];
    wire signed [WD:0] diff = $signed({in_pix[WD-1], in_pix}) - $signed({b[WD-1], b});
    wire signed [WD-1:0] e = (diff > $signed({2'b00, {(WD-1){1'b1}}})) ? {1'b0, {(WD-1){1'b1}}} :
                             (diff < $signed({2'b11, {(WD-1){1'b0}}})) ? {1'b1, {(WD-1){1'b0}}} : diff[WD-1:0];
    wire signed [WB-1:0] e_w = e;
    wire [WD-1:0] ae = e[WD-1] ? -e : e;
    wire signed [WB-1:0] step = (MODE == 0) ? e_w :
                                (MODE == 1) ? ((e > 0) ? (1 <<< SK) : (e < 0) ? -(1 <<< SK) : 0) :
                                ((ae < TAU) ? e_w : 0);

    always @(posedge clk) begin
        out_valid <= 1'b0;
        if (rst) begin
            col <= 0; Bacc <= 0; out_pix <= 0; out_bias <= 0;
        end else if (in_valid) begin
            Bacc <= bacc_eff + step;
            out_valid <= 1'b1;
            out_pix <= e;
            out_bias <= b;
            col <= (col == W - 1) ? 0 : col + 1'b1;
        end
    end
endmodule
