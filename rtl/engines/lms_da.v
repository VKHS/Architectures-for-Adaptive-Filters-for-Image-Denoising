// lms_da: multiplier-free block LMS with a distributed-arithmetic (DA) filter.
//
// The taps are split into NG = ceil(L/K) groups of K = 4. Each group keeps a 16-word table of all partial sums
// of its four weights, T_g[a] = sum_i a_i w_(4g+i). Writing every tap in two's complement,
//     x_k = -x_k[WD-1] 2^(WD-1) + sum_(b < WD-1) x_k[b] 2^b,
// the inner product becomes  y_acc = sum_b s_b 2^b sum_g T_g[ x_(4g+3)[b] .. x_(4g)[b] ],  s_b = -1 for the MSB:
// one table look-up per group and bit, an NG-input adder tree and one shift-accumulator (Horner, MSB first).
// The result is the exact integer inner product, so the engine is bit-exact with lms_rowblock.
//
// The weights change only at the end of a block (in_last), so the tables are rebuilt only then (16 cycles).
// The gradient needs no multiplier either: RULE = 0 forms e*x_k bit-serially over the bits of e (one adder
// per tap, overlapped with the next sample's filter), RULE = 1 (sign-error) adds +-x_k << FD.
// Initiation interval: WD + T + 3 cycles (T = ceil(log2 NG)); a row end adds the commit and the rebuild.
module lms_da #(
    parameter L = 8, RULE = 0,
    parameter WD = 16, FD = 12, WW = 24, FW = 20, WA = 48, S = 7, LEAK = 0,
    parameter OUT = 0, GATED = 0, GKS = 2, GRATE = 7, GFRAC = 8,
    parameter integer TMIN = 410, S0 = 205,
    parameter [WA-1:0] A0 = 0
)(
    input  wire clk, rst,
    input  wire in_valid,
    output wire in_ready,
    input  wire [L*WD-1:0] in_x,
    input  wire signed [WD-1:0] in_d, in_p,
    input  wire in_adapt, in_last,
    output reg  out_valid,
    output reg  signed [WD-1:0] out_o, out_y, out_e,
    output reg  out_flag
);
    `include "lms_arith.vh"
    function integer clog2;
        input integer v;
        integer t;
        begin
            clog2 = 0;
            for (t = v - 1; t > 0; t = t >> 1) clog2 = clog2 + 1;
        end
    endfunction
    localparam K  = 4;
    localparam NG = (L + K - 1) / K;
    localparam LP = NG * K;
    localparam T  = clog2(NG);
    localparam BW = clog2(WD + 1);
    localparam WT = WW + 2;
    localparam TM = (T > 0) ? T - 1 : 0;

    localparam [2:0] CLR = 3'd0, BUILD = 3'd1, IDLE = 3'd2, BITS = 3'd3, TAIL = 3'd4, ERR = 3'd5,
                     WAITG = 3'd6, COMMIT = 3'd7;
    reg [2:0] state;
    reg [BW-1:0] bit_i;                  // bit being looked up (MSB first)
    reg [4:0] cnt;                       // build address / tail counter
    reg signed [WD-1:0] xr [0:LP-1];     // taps of the sample being filtered
    reg signed [WD-1:0] dr, pr;
    reg ar, lr;
    reg signed [WA-1:0] A [0:LP-1];
    reg signed [WA-1:0] hacc;            // Horner shift-accumulator
    integer i;

    // ------------------------------------------------------------------ DA tables and look-ups
    wire [NG*WA-1:0] looked;
    genvar g;
    generate
        for (g = 0; g < NG; g = g + 1) begin : grp
            reg signed [WT-1:0] Tg [0:15];
            reg signed [WA-1:0] lk;
            wire [3:0] addr = {xr[4*g+3][bit_i], xr[4*g+2][bit_i], xr[4*g+1][bit_i], xr[4*g][bit_i]};
            wire signed [WW-1:0] w0 = view(A[4*g]),   w1 = view(A[4*g+1]);
            wire signed [WW-1:0] w2 = view(A[4*g+2]), w3 = view(A[4*g+3]);
            wire signed [WT-1:0] entry = (cnt[0] ? w0 : 0) + (cnt[1] ? w1 : 0) + (cnt[2] ? w2 : 0) +
                                         (cnt[3] ? w3 : 0);
            always @(posedge clk) begin
                if (state == BUILD) Tg[cnt[3:0]] <= entry;
                lk <= Tg[addr];
            end
            assign looked[g*WA +: WA] = lk;
        end
    endgenerate
    wire signed [WA-1:0] bitsum;
    adder_tree #(.N(NG), .W(WA)) tree (.clk(clk), .en(1'b1), .in(looked), .out(bitsum));

    // valid / MSB marks travelling with the look-up (1 register) and the tree (T registers)
    reg [T:0] pv, pm;
    always @(posedge clk) begin
        pv <= {pv[TM:0], (state == BITS)};
        pm <= {pm[TM:0], (state == BITS) && (bit_i == WD - 1)};
        if (rst) begin pv <= 0; pm <= 0; end
    end
    wire bit_out = pv[T], msb_out = pm[T];

    // ------------------------------------------------------------------ error unit
    wire signed [WD-1:0] y_c = y_of(hacc + RND);
    wire signed [WD-1:0] e_c, o_c;
    wire f_c, a_c;
    lms_err_unit #(.WD(WD), .OUT(OUT), .GATED(GATED), .GKS(GKS), .GRATE(GRATE), .GFRAC(GFRAC),
                   .TMIN(TMIN), .S0(S0)) eu (
        .clk(clk), .rst(rst), .en(state == ERR), .y(y_c), .d(dr), .p(pr), .adapt_in(ar),
        .e(e_c), .o(o_c), .flag(f_c), .adapt_out(a_c));

    // ------------------------------------------------------------------ bit-serial gradient (overlapped)
    reg signed [WD-1:0] eg;
    reg signed [WD-1:0] xg [0:LP-1];
    reg [BW-1:0] gbit;
    reg gbusy, gadd, glast;
    reg signed [2*WD:0] tk [0:LP-1];
    reg signed [WA-1:0] G [0:LP-1];
    wire gdone = gbusy && ((RULE != 0) || gbit == 0);

    assign in_ready = (state == IDLE);

    always @(posedge clk) begin
        out_valid <= 1'b0;
        if (rst) begin
            state <= CLR; cnt <= 0; bit_i <= 0; hacc <= 0; dr <= 0; pr <= 0; ar <= 1'b0; lr <= 1'b0;
            gbusy <= 1'b0; gadd <= 1'b0; glast <= 1'b0; gbit <= 0; eg <= 0;
            out_o <= 0; out_y <= 0; out_e <= 0; out_flag <= 1'b0;
            for (i = 0; i < LP; i = i + 1) begin A[i] <= A0; G[i] <= 0; end
        end else begin
            // Horner accumulation of the tree output, MSB first
            if (bit_out) hacc <= msb_out ? -bitsum : (hacc <<< 1) + bitsum;

            // gradient: one bit of e per cycle (RULE 0) or one cycle (RULE 1)
            if (gbusy) begin
                for (i = 0; i < LP; i = i + 1)
                    if (RULE != 0)
                        tk[i] <= (eg > 0) ? (xg[i] <<< FD) : (eg < 0) ? -(xg[i] <<< FD) : 0;
                    else
                        tk[i] <= ((gbit == WD - 1) ? 0 : (tk[i] <<< 1)) +
                                 (eg[gbit] ? ((gbit == WD - 1) ? -xg[i] : xg[i]) : 0);
                if (gdone) begin gbusy <= 1'b0; gadd <= 1'b1; end
                else gbit <= gbit - 1'b1;
            end
            if (gadd) begin
                gadd <= 1'b0;
                for (i = 0; i < LP; i = i + 1)
                    if (glast) G[i] <= 0; else G[i] <= G[i] + tk[i];
                if (glast)
                    for (i = 0; i < LP; i = i + 1) A[i] <= upd(A[i], G[i] + tk[i]);
            end

            case (state)
                CLR: begin cnt <= 0; state <= BUILD; end
                BUILD: if (cnt == 15) begin cnt <= 0; state <= IDLE; end else cnt <= cnt + 1'b1;
                IDLE: if (in_valid) begin
                    for (i = 0; i < LP; i = i + 1) xr[i] <= (i < L) ? in_x[i*WD +: WD] : {WD{1'b0}};
                    dr <= in_d; pr <= in_p; ar <= in_adapt; lr <= in_last;
                    bit_i <= WD - 1;
                    state <= BITS;
                end
                BITS: if (bit_i == 0) begin cnt <= 0; state <= TAIL; end else bit_i <= bit_i - 1'b1;
                TAIL: if (cnt == T) state <= ERR; else cnt <= cnt + 1'b1;
                ERR: begin
                    out_valid <= 1'b1;
                    out_o <= o_c; out_y <= y_c; out_e <= e_c; out_flag <= f_c;
                    // start this sample's gradient (a sample that does not adapt adds zero)
                    eg <= a_c ? e_c : {WD{1'b0}};
                    for (i = 0; i < LP; i = i + 1) xg[i] <= xr[i];
                    gbit <= WD - 1; gbusy <= 1'b1; glast <= lr;
                    state <= lr ? WAITG : IDLE;
                end
                WAITG: if (gadd) state <= COMMIT;
                COMMIT: begin cnt <= 0; state <= BUILD; end
                default: state <= IDLE;
            endcase
        end
    end
endmodule
