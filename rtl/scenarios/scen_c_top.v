// Scenario C: periodic interference without a reference (two-band delayed-reference canceller), row by row.
//
//   1. a row enters one of two row buffers (ping-pong), so the next row can arrive while one is processed
//   2. HB phase:  h(j) = z(j) - lowpass(z)(j), 33-tap symmetric Gaussian (sigma 4, Q16 coefficients that sum
//                 to exactly 1), reflect borders: the buffer is read at refl(t), t = -16 .. W+15; 17 multipliers
//                 after the pre-adders, an adder tree, rounding. h goes to a third buffer.
//   3. CANCEL phase: steps t = -(L-1) .. W-1 feed the newest tap x0(t) = h(refl(t - DELAY)) (a V-shaped read
//                 order at the start of the row, which is the software's reflected history); t < 0 are pre-roll
//                 shifts, t >= 0 are samples with d = h(t) and p = z(t). The engine output is p - y.
// Pipelined engines keep the tapped delay line inside (TDL = 1) and get DRAIN_ROW drain steps after each row;
// handshake engines get the tap vector from a delay line kept here. Model: afarch.scenarios.scenario_c.
module scen_c_top #(
    parameter W = 64, HH = 8, L = 16, DELAY = 8,
    parameter ENGINE = 0, P = 2,
    parameter WD = 16, FD = 12, WW = 24, FW = 20, WA = 48, S = 7, RULE = 0, LEAK = 0,
    parameter DRAIN_ROW = 0, DRAIN_FRAME = 64
)(
    input  wire clk, rst,
    input  wire in_valid,
    output wire in_ready,
    input  wire signed [WD-1:0] in_pix,
    output wire out_valid,
    output wire signed [WD-1:0] out_pix
);
    function integer clog2;
        input integer v;
        integer t;
        begin
            clog2 = 1;
            for (t = v - 1; t > 1; t = t >> 1) clog2 = clog2 + 1;
        end
    endfunction
    localparam GH = 16, GF = 16;                    // Gaussian half-width and coefficient fraction bits
    localparam CW = clog2(W + 2 * L + 2 * GH + 4) + 1;
    localparam AW = clog2(W);
    localparam PIPE = (ENGINE >= 2 && ENGINE <= 4);
    localparam TG = clog2(GH + 1);                  // adder-tree levels of the Gaussian (17 inputs -> 5)

    // afarch.frontends.gauss_kernel(4.0, 16, 16): g[0] is the centre, g[m] = g[-m]
    function integer gcoef;
        input integer m;
        case (m)
            0: gcoef = 6536;  1: gcoef = 6335;  2: gcoef = 5768;  3: gcoef = 4934;  4: gcoef = 3965;
            5: gcoef = 2993;  6: gcoef = 2122;  7: gcoef = 1414;  8: gcoef = 885;   9: gcoef = 520;
            10: gcoef = 287;  11: gcoef = 149;  12: gcoef = 73;   13: gcoef = 33;   14: gcoef = 14;
            15: gcoef = 6;    16: gcoef = 2;
            default: gcoef = 0;
        endcase
    endfunction
    function integer refl;
        input integer t, n;
        begin
            refl = (t < 0) ? -t : (t > n - 1) ? 2 * (n - 1) - t : t;
        end
    endfunction

    // ------------------------------------------------------------------ input: ping-pong row buffers
    reg [WD-1:0] zb0 [0:W-1];
    reg [WD-1:0] zb1 [0:W-1];
    reg wsel, psel;
    reg [1:0] full;
    reg [CW-1:0] icol;
    assign in_ready = !full[wsel];
    wire wr = in_valid && in_ready;
    always @(posedge clk) if (wr) begin
        if (wsel) zb1[icol] <= in_pix; else zb0[icol] <= in_pix;
    end

    // ------------------------------------------------------------------ processing state machine
    localparam [2:0] IDLE = 3'd0, HB = 3'd1, HBW = 3'd2, CAN = 3'd3, DRN = 3'd4;
    reg [2:0] st;
    reg [15:0] cnt;
    reg [15:0] crow;

    // z buffer read port (HB phase: refl(ht); CANCEL phase: p at ct)
    reg signed [CW-1:0] ht, ct;
    reg [WD-1:0] zq;
    wire z_issue_hb;
    wire z_issue_can;
    wire [AW-1:0] z_addr = (st == HB) ? refl(ht, W) : ct[AW-1:0];
    wire z_re = z_issue_hb | z_issue_can;
    always @(posedge clk) if (z_re) zq <= psel ? zb1[z_addr] : zb0[z_addr];

    // ------------------------------------------------------------------ HB phase: Gaussian high band
    reg signed [WD-1:0] hw [0:2*GH];
    reg hrd_v;
    reg [CW-1:0] hfill;
    reg hwin_v;
    reg [AW-1:0] hj_next, hj_win;
    assign z_issue_hb = (st == HB) && (ht <= W - 1 + GH);
    integer i;
    always @(posedge clk) begin
        hrd_v <= z_issue_hb;
        hwin_v <= 1'b0;
        if (hrd_v) begin
            for (i = 0; i < 2 * GH; i = i + 1) hw[i] <= hw[i+1];
            hw[2*GH] <= zq;
            hfill <= hfill + 1'b1;
            if (hfill >= 2 * GH) begin hwin_v <= 1'b1; hj_win <= hj_next; hj_next <= hj_next + 1'b1; end
        end
        if (st == IDLE) begin hfill <= 0; hj_next <= 0; end
    end
    // products after the pre-adders (registered), adder tree, rounding, h = z - lowpass
    wire [(GH+1)*WA-1:0] gprod;
    reg  [(GH+1)*WA-1:0] gprod_q;
    genvar gm;
    generate
        for (gm = 0; gm <= GH; gm = gm + 1) begin : gp
            // $signed on the concatenation keeps the whole conditional signed, so the pre-adder sign-extends
            wire signed [WD:0] pre = (gm == 0) ? $signed({hw[GH][WD-1], hw[GH]}) : hw[GH-gm] + hw[GH+gm];
            wire signed [WA-1:0] c = gcoef(gm);
            assign gprod[gm*WA +: WA] = (gm == 0) ? (c * pre + (1 <<< (GF - 1))) : c * pre;
        end
    endgenerate
    reg [TG:0] hv_pipe;
    reg [AW-1:0] hj_pipe [0:TG];
    reg signed [WD-1:0] hz_pipe [0:TG];
    always @(posedge clk) begin
        gprod_q <= gprod;
        hv_pipe <= {hv_pipe[TG-1:0], hwin_v};
        hj_pipe[0] <= hj_win;
        hz_pipe[0] <= hw[GH];
        for (i = 1; i <= TG; i = i + 1) begin hj_pipe[i] <= hj_pipe[i-1]; hz_pipe[i] <= hz_pipe[i-1]; end
        if (rst) hv_pipe <= 0;
    end
    wire signed [WA-1:0] gsum;
    adder_tree #(.N(GH + 1), .W(WA)) gtree (.clk(clk), .en(1'b1), .in(gprod_q), .out(gsum));
    wire signed [WA-1:0] lp = gsum >>> GF;
    wire signed [WA-1:0] hdiff = $signed({{(WA-WD){hz_pipe[TG][WD-1]}}, hz_pipe[TG]}) - lp;
    wire signed [WD-1:0] hval = (hdiff > $signed({{(WA-WD+1){1'b0}}, {(WD-1){1'b1}}})) ? {1'b0, {(WD-1){1'b1}}} :
                                (hdiff < $signed({{(WA-WD+1){1'b1}}, {(WD-1){1'b0}}})) ? {1'b1, {(WD-1){1'b0}}} :
                                hdiff[WD-1:0];
    wire h_we = hv_pipe[TG];

    // high-band buffer: write port A (HB phase), read port A (d) and read port B (x0) in the CANCEL phase
    reg [WD-1:0] hb [0:W-1];
    reg [WD-1:0] hqa, hqb;
    wire h_re;
    wire signed [CW-1:0] xt = ct - DELAY;
    always @(posedge clk) begin
        if (h_we) hb[hj_pipe[TG]] <= hval;
        if (h_re) begin
            hqa <= hb[ct[AW-1:0]];
            hqb <= hb[refl(xt, W)];
        end
    end

    // ------------------------------------------------------------------ CANCEL phase: steps and the engine
    reg ex_v, ex_s, ex_last;                          // exec stage: occupied, sample (vs pre-roll), row end
    wire e_ready;
    wire ex_done = !ex_v || PIPE || !ex_s || e_ready;
    wire more = (st == CAN) && (ct <= W - 1);
    assign h_re = more && ex_done;
    assign z_issue_can = h_re && (ct >= 0);
    reg [L*WD-1:0] tdl;                               // handshake engines: the tapped delay line
    wire [L*WD-1:0] vec = {tdl[(L-1)*WD-1:0], hqb};
    wire signed [WD-1:0] x0 = hqb;
    wire signed [WD-1:0] dd = hqa;
    wire signed [WD-1:0] pp = zq;
    wire last_row = (crow == HH - 1);
    reg  [15:0] dcnt;
    wire e_drain = PIPE && (st == DRN) && (dcnt != 0);
    wire e_valid = ex_v && ex_s;
    wire e_shift = ex_v && !ex_s && PIPE;

    always @(posedge clk) begin
        if (rst) begin
            st <= IDLE; full <= 2'b00; wsel <= 1'b0; psel <= 1'b0; icol <= 0; crow <= 0;
            ht <= 0; ct <= 0; cnt <= 0; ex_v <= 1'b0; ex_s <= 1'b0; ex_last <= 1'b0; dcnt <= 0;
            tdl <= 0;
        end else begin
            // input side
            if (wr) begin
                if (icol == W - 1) begin icol <= 0; full[wsel] <= 1'b1; wsel <= ~wsel; end
                else icol <= icol + 1'b1;
            end
            case (st)
                IDLE: if (full[psel]) begin ht <= -GH; st <= HB; end
                HB: begin
                    if (z_issue_hb) ht <= ht + 1'b1;
                    else begin cnt <= 0; st <= HBW; end
                end
                HBW: if (cnt == TG + 6) begin ct <= -(L - 1); st <= CAN; end else cnt <= cnt + 1'b1;
                CAN: begin
                    if (ex_done) begin
                        if (ex_v && !PIPE) tdl <= vec;
                        ex_v <= h_re;
                        ex_s <= (ct >= 0);
                        ex_last <= (ct == W - 1);
                        if (h_re) ct <= ct + 1'b1;
                        if (!h_re && (!ex_v || ex_done)) begin
                            dcnt <= last_row ? DRAIN_FRAME : DRAIN_ROW;
                            st <= DRN;
                        end
                    end
                end
                DRN: if (dcnt != 0) dcnt <= dcnt - 1'b1;
                     else begin
                         full[psel] <= 1'b0; psel <= ~psel;
                         crow <= last_row ? 0 : crow + 1'b1;
                         st <= IDLE;
                     end
            endcase
        end
    end

    // ------------------------------------------------------------------ engine (output p - y)
    wire eo_valid, eo_flag;
    wire signed [WD-1:0] eo_o, eo_y, eo_e;
    lms_engine #(.ENGINE(ENGINE), .L(L), .P(P), .TDL(PIPE ? 1 : 0), .WD(WD), .FD(FD), .WW(WW), .FW(FW), .WA(WA),
                 .S(S), .RULE(RULE), .LEAK(LEAK), .OUT(2)) eng (
        .clk(clk), .rst(rst), .in_valid(e_valid), .in_shift(e_shift), .in_drain(e_drain), .in_ready(e_ready),
        .in_x(PIPE ? {{((L-1)*WD){1'b0}}, x0} : vec), .in_d(dd), .in_p(pp), .in_adapt(1'b1), .in_last(ex_last),
        .out_valid(eo_valid), .out_o(eo_o), .out_y(eo_y), .out_e(eo_e), .out_flag(eo_flag));
    assign out_valid = eo_valid;
    assign out_pix = eo_o;
endmodule
