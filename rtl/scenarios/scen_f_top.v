// Scenario F: reference-sensor canceller. Every row arrives as NOB optical-black (OB) pixels, which see the row's
// offset but no light, followed by W scene pixels; a concurrent reference channel (in_ref) may come with every
// scene pixel (e.g. a reference output that sees only the readout telegraph noise).
//
//   x_ob  = (sum of the row's OB pixels) >>> LOGNOB             one adder, no division (NOB = 2^LOGNOB)
//   x     = XSEL ? in_ref : x_ob,   d = scene pixel,  out = e = d - w x
//   mode 0  frozen     : no adaptation (the weight was calibrated before)
//   mode 1  calibrate  : adapt on every scene pixel (run this on dark frames: the scene is absent there)
//   mode 2  OB online  : after the OB pixels, adapt on each of them with the leave-one-out reference
//                        x_k = (sum - ob_k) / (NOB - 1) (constant multiply), then correct the scene row frozen
// The engine is any of the six (one tap). A tag FIFO marks which engine outputs are scene pixels.
// Model: sim/test_scenarios.py (case_f) composes afarch.engines.Engine in the same order.
module scen_f_top #(
    parameter W = 64, NOB = 16, LOGNOB = 4, XSEL = 0,
    parameter ENGINE = 0, P = 1,
    parameter WD = 16, FD = 12, WW = 24, FW = 20, WA = 48, S = 1, RULE = 0, LEAK = 0,
    parameter DRAIN_ROW = 0
)(
    input  wire clk, rst,
    input  wire [1:0] mode,
    input  wire in_valid,
    output wire in_ready,
    input  wire signed [WD-1:0] in_pix, in_ref,
    input  wire in_flush,                 // drain the pipelined engines (end of a frame)
    output wire out_valid,
    output wire signed [WD-1:0] out_pix
);
    localparam PIPE = (ENGINE >= 2 && ENGINE <= 4);
    localparam integer INV = (4096 + (NOB - 1) / 2) / (NOB - 1);    // round(2^12 / (NOB - 1))

    reg [15:0] col;
    reg signed [WD+LOGNOB+1:0] obsum;
    reg signed [WD-1:0] ob [0:NOB-1];
    reg signed [WD-1:0] x_ob;
    reg [7:0] lk;                         // leave-one-out step being issued, NOB = done
    reg [15:0] drain_cnt;
    wire draining = (drain_cnt != 0);
    wire e_ready;

    // the engine sample offered this cycle
    wire in_ob = (col < NOB);
    wire loo = (mode == 2) && (lk < NOB);                         // leave-one-out updates pending
    wire signed [WD+LOGNOB+1:0] loo_num = obsum - ob[lk[LOGNOB-1:0]];
    wire signed [WD+LOGNOB+15:0] loo_prod = loo_num * INV;
    wire signed [WD-1:0] x_loo = loo_prod >>> 12;
    wire scene = !in_ob && in_valid && !loo;
    wire e_valid = !draining && (loo || scene);
    wire signed [WD-1:0] e_x = loo ? x_loo : (XSEL ? in_ref : x_ob);
    wire signed [WD-1:0] e_d = loo ? ob[lk[LOGNOB-1:0]] : in_pix;
    wire e_adapt = loo || (mode == 1);
    wire e_last = scene && (col == NOB + W - 1);
    wire take = e_valid && e_ready;

    assign in_ready = !draining && (in_ob || (!loo && e_ready));
    wire wr = in_valid && in_ready;

    // tag FIFO: 1 = a scene pixel (its output leaves the top), 0 = a leave-one-out update (output dropped)
    reg tagq [0:63];
    reg [5:0] tw, tr;
    always @(posedge clk) begin
        if (rst) begin
            col <= 0; obsum <= 0; x_ob <= 0; lk <= NOB; drain_cnt <= 0; tw <= 0;
        end else begin
            if (take) begin tagq[tw] <= scene; tw <= tw + 1'b1; end
            if (take && loo) lk <= lk + 1'b1;
            if (wr) begin
                if (in_ob) begin
                    ob[col[LOGNOB-1:0]] <= in_pix;
                    obsum <= (col == 0 ? 0 : obsum) + in_pix;
                    if (col == NOB - 1) begin
                        x_ob <= ((col == 0 ? 0 : obsum) + in_pix) >>> LOGNOB;
                        lk <= 0;
                    end
                end
                col <= (col == NOB + W - 1) ? 0 : col + 1'b1;
            end
            if (take && e_last && PIPE) drain_cnt <= DRAIN_ROW;
            else if (in_flush && PIPE && !draining) drain_cnt <= 64;
            else if (draining) drain_cnt <= drain_cnt - 1'b1;
        end
    end

    wire eo_valid, eo_flag;
    wire signed [WD-1:0] eo_o, eo_y, eo_e;
    lms_engine #(.ENGINE(ENGINE), .L(1), .P(P), .WD(WD), .FD(FD), .WW(WW), .FW(FW), .WA(WA), .S(S), .RULE(RULE),
                 .LEAK(LEAK), .OUT(0)) eng (
        .clk(clk), .rst(rst), .in_valid(e_valid), .in_shift(1'b0), .in_drain(draining), .in_ready(e_ready),
        .in_x(e_x), .in_d(e_d), .in_p(e_d), .in_adapt(e_adapt), .in_last(e_last), .out_valid(eo_valid),
        .out_o(eo_o), .out_y(eo_y), .out_e(eo_e), .out_flag(eo_flag));

    always @(posedge clk)
        if (rst) tr <= 0;
        else if (eo_valid) tr <= tr + 1'b1;
    assign out_valid = eo_valid && tagq[tr];
    assign out_pix = eo_o;
endmodule
