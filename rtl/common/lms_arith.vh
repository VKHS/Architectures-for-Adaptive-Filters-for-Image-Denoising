// Fixed-point arithmetic shared by all LMS engines (bit-exact with afarch/fxp.py).
// `include this file inside a module body, after the parameters WD, FD, WW, FW, WA, S, RULE, LEAK.
//
//   data x, d, y, e : signed WD bits, FD fractional bits
//   weight view w    : signed WW bits, FW fractional bits, w = sat_WW(A >>> VSH)
//   accumulator A    : signed WA bits, holds the exact sum of update products g (2*FD fractional bits)
//   step             : mu = 2^-S is the choice of the bit slice VSH = 2*FD - FW + S
//   RULE             : 0 LMS g = e*x, 1 sign-error, 2 sign-data, 3 sign-sign
//   LEAK             : 0 none, else A <- A - (A >>> LEAK) + g on each applied update

localparam integer VSH = 2*FD - FW + S;
localparam signed [WA-1:0] RND  = {{(WA-FW){1'b0}}, 1'b1, {(FW-1){1'b0}}};   // 2^(FW-1)
localparam signed [WA-1:0] DMAX = {{(WA-WD+1){1'b0}}, {(WD-1){1'b1}}};
localparam signed [WA-1:0] DMIN = {{(WA-WD+1){1'b1}}, {(WD-1){1'b0}}};
localparam signed [WA-1:0] WMAX = {{(WA-WW+1){1'b0}}, {(WW-1){1'b1}}};
localparam signed [WA-1:0] WMIN = {{(WA-WW+1){1'b1}}, {(WW-1){1'b0}}};

// saturate a WA-bit value to WD bits
function signed [WD-1:0] sat_d;
    input signed [WA-1:0] a;
    begin
        if (a > DMAX)      sat_d = DMAX[WD-1:0];
        else if (a < DMIN) sat_d = DMIN[WD-1:0];
        else               sat_d = a[WD-1:0];
    end
endfunction

// weight view of an accumulator
function signed [WW-1:0] view;
    input signed [WA-1:0] acc;
    reg signed [WA-1:0] t;
    begin
        t = acc >>> VSH;
        if (t > WMAX)      view = WMAX[WW-1:0];
        else if (t < WMIN) view = WMIN[WW-1:0];
        else               view = t[WW-1:0];
    end
endfunction

// filter output from an accumulated (and RND-preloaded) inner product
function signed [WD-1:0] y_of;
    input signed [WA-1:0] acc;
    begin
        y_of = sat_d(acc >>> FW);
    end
endfunction

// e = sat(d - y)
function signed [WD-1:0] err_of;
    input signed [WD-1:0] d, y;
    reg signed [WA-1:0] t;
    begin
        t = d;
        t = t - y;
        err_of = sat_d(t);
    end
endfunction

// update product for one tap
function signed [WA-1:0] grad;
    input signed [WD-1:0] e, x;
    reg signed [WA-1:0] ew, xw;
    reg signed [2*WD-1:0] pr;
    begin
        ew = e;
        xw = x;
        pr = e * x;
        case (RULE)
            0: grad = pr;
            1: grad = (e > 0) ? (xw <<< FD) : (e < 0) ? -(xw <<< FD) : {WA{1'b0}};
            2: grad = (x > 0) ? (ew <<< FD) : (x < 0) ? -(ew <<< FD) : {WA{1'b0}};
            default: grad = ((e > 0 && x > 0) || (e < 0 && x < 0)) ? ({{(WA-1){1'b0}}, 1'b1} <<< (2*FD)) :
                            ((e > 0 && x < 0) || (e < 0 && x > 0)) ? -({{(WA-1){1'b0}}, 1'b1} <<< (2*FD)) :
                            {WA{1'b0}};
        endcase
    end
endfunction

// one applied update
function signed [WA-1:0] upd;
    input signed [WA-1:0] acc, g;
    begin
        if (LEAK > 0) upd = acc - (acc >>> LEAK) + g;
        else          upd = acc + g;
    end
endfunction
