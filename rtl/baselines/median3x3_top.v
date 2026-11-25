// Non-adaptive baselines on the same window generator: 3 x 3 median and switching median.
//
// The median of the nine window pixels comes from the 19 compare-exchange network of Paeth / Devillard
// (opt_med9); a compare-exchange is a comparator and two multiplexers, no arithmetic. SWITCH = 1 keeps the
// centre pixel unless it differs from the median by more than THR (a switching median: only outliers change).
// Borders are reflected (scipy.ndimage.median_filter(mode="mirror")). One window per clock.
module median3x3_top #(
    parameter W = 64, HH = 64, WD = 16, SWITCH = 0,
    parameter integer THR = 410
)(
    input  wire clk, rst,
    input  wire in_valid,
    output wire in_ready,
    input  wire signed [WD-1:0] in_pix,
    output reg  out_valid,
    output reg  signed [WD-1:0] out_pix,
    output reg  out_flag
);
    wire w_valid, w_last, w_eof;
    wire [9*WD-1:0] win;
    wire [WD-1:0] ctr;
    window_gen #(.W(W), .HH(HH), .R(1), .WD(WD), .PL(1)) wg (
        .clk(clk), .rst(rst), .in_valid(in_valid), .in_ready(in_ready), .in_pix(in_pix),
        .out_valid(w_valid), .out_ready(1'b1), .out_win(win), .out_ctr(ctr), .out_last(w_last), .out_eof(w_eof));

    function signed [WD-1:0] med9;
        input [9*WD-1:0] v;
        reg signed [WD-1:0] p [0:8];
        reg signed [WD-1:0] t;
        integer i;
        begin
            for (i = 0; i < 9; i = i + 1) p[i] = v[i*WD +: WD];
            `define CX(a, b) if (p[a] > p[b]) begin t = p[a]; p[a] = p[b]; p[b] = t; end
            `CX(1, 2) `CX(4, 5) `CX(7, 8)
            `CX(0, 1) `CX(3, 4) `CX(6, 7)
            `CX(1, 2) `CX(4, 5) `CX(7, 8)
            `CX(0, 3) `CX(5, 8) `CX(4, 7)
            `CX(3, 6) `CX(1, 4) `CX(2, 5)
            `CX(4, 7) `CX(4, 2) `CX(6, 4)
            `CX(4, 2)
            `undef CX
            med9 = p[4];
        end
    endfunction

    wire signed [WD-1:0] m = med9(win);
    wire signed [WD-1:0] c = ctr;
    wire signed [WD:0] dev = $signed({c[WD-1], c}) - $signed({m[WD-1], m});
    wire outlier = (dev > THR) || (dev < -THR);
    always @(posedge clk) begin
        out_valid <= !rst && w_valid;
        out_pix <= (SWITCH == 0) ? m : (outlier ? m : c);
        out_flag <= (SWITCH == 0) ? 1'b1 : outlier;
    end
endmodule
