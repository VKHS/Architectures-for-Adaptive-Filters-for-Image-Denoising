// Error unit shared by all engines: e = sat(d - y), the optional robust gate, and the output selector.
// Combinational, except for the gate's running scale s, which advances when en = 1 (a valid sample here).
//
//   OUT = 0 : o = e            (cancellers: A, C with p = d, F)
//   OUT = 1 : o = y            (predictors: D, E)
//   OUT = 2 : o = sat(p - y)   (C: subtract the predicted interference from the full-band pixel p)
//   OUT = 3 : o = flag ? y : p (gated D: replace only flagged pixels)
//
// Gate (GATED = 1): flag = |e| > max((s >>> GFRAC) <<< GKS, TMIN); on unflagged samples
//                   s <- s + ((1.5|e| << GFRAC) - s) >>> GRATE. Bit-exact with afarch.engines.Gate.
module lms_err_unit #(
    parameter WD = 16, OUT = 0, GATED = 0,
    parameter GKS = 2, GRATE = 7, GFRAC = 8,
    parameter integer TMIN = 410, S0 = 205
)(
    input  wire clk, rst, en,
    input  wire signed [WD-1:0] y, d, p,
    input  wire adapt_in,
    output wire signed [WD-1:0] e, o,
    output wire flag, adapt_out
);
    localparam WS = WD + GFRAC + 3;
    localparam signed [WD:0] EMAX = (1 <<< (WD-1)) - 1;
    localparam signed [WD:0] EMIN = -(1 <<< (WD-1));

    wire signed [WD:0] diff = $signed({d[WD-1], d}) - $signed({y[WD-1], y});
    assign e = (diff > EMAX) ? EMAX[WD-1:0] : (diff < EMIN) ? EMIN[WD-1:0] : diff[WD-1:0];

    wire signed [WD:0] pdiff = $signed({p[WD-1], p}) - $signed({y[WD-1], y});
    wire signed [WD-1:0] p_y = (pdiff > EMAX) ? EMAX[WD-1:0] : (pdiff < EMIN) ? EMIN[WD-1:0] : pdiff[WD-1:0];

    reg  signed [WS-1:0] s;
    wire [WD-1:0] ae = e[WD-1] ? -e : e;                       // |e| fits: e > EMIN after a subtraction of
    wire signed [WS-1:0] thr_s = (s >>> GFRAC) <<< GKS;         // two in-range values except e = EMIN
    wire signed [WS-1:0] thr = (thr_s > TMIN) ? thr_s : TMIN;
    wire signed [WS-1:0] ae_w = {{(WS-WD){1'b0}}, ae};
    assign flag = (GATED != 0) && (ae_w > thr);
    assign adapt_out = adapt_in && !flag;

    wire signed [WS-1:0] target = (ae_w + (ae_w >>> 1)) <<< GFRAC;
    always @(posedge clk) begin
        if (rst) s <= S0 <<< GFRAC;
        else if (en && GATED != 0 && !flag) s <= s + ((target - s) >>> GRATE);
    end

    assign o = (OUT == 0) ? e : (OUT == 1) ? y : (OUT == 2) ? p_y : (flag ? y : p);
endmodule
