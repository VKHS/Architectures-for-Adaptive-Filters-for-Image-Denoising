// window_gen: raster stream -> (2R+1) x (2R+1) windows with whole-sample reflection at all four borders.
//
// Write side: rows go round-robin into NB = 2R+2 row buffers (one block RAM each for W <= 1024 at 18 bits).
// Read side: an address generator. For output row i, window row a reads image row refl(i + a); the columns
// are read in the order refl(-R), ..., refl(W-1+R), every buffer at the same column address, and shifted into
// a register window. Reading refl(t) instead of t makes the border padding free: no extra storage, no muxes
// on the window. Each row costs W + 2R read cycles; output row i starts once input row min(i+R, HH-1) is
// complete, and the input may run at most R+1 rows ahead of the output (in_ready), so a row buffer is never
// overwritten while it is still needed. One frame at a time: the next frame is accepted after the last window.
//
// Planes: PL planes of WD bits travel together (plane 0 = taps; other planes, e.g. the desired sample, are
// delivered only at the window centre, out_ctr).
module window_gen #(
    parameter W = 64, HH = 64, R = 2, WD = 16, PL = 2
)(
    input  wire clk, rst,
    input  wire in_valid,
    output wire in_ready,
    input  wire [PL*WD-1:0] in_pix,
    output reg  out_valid,
    input  wire out_ready,
    output wire [(2*R+1)*(2*R+1)*WD-1:0] out_win,
    output wire [PL*WD-1:0] out_ctr,
    output reg  out_last, out_eof
);
    function integer clog2;
        input integer v;
        integer t;
        begin
            clog2 = 1;
            for (t = v - 1; t > 1; t = t >> 1) clog2 = clog2 + 1;
        end
    endfunction
    localparam K  = 2 * R + 1;
    localparam NB = 2 * R + 2;
    localparam CW = clog2(W + 2 * R + 2) + 1;      // signed column index
    localparam RW = clog2(HH + 2 * R + 2) + 1;     // signed row index
    localparam AW = clog2(W);

    function integer refl;                        // whole-sample reflection into [0, n-1]
        input integer t, n;
        begin
            refl = (t < 0) ? -t : (t > n - 1) ? 2 * (n - 1) - t : t;
        end
    endfunction

    // ------------------------------------------------------------------------------ write side
    reg [CW-1:0] icol;
    reg [RW-1:0] irow;                            // rows completely written in this frame
    reg [RW-1:0] orow;                            // output row in progress
    reg frame_done;
    assign in_ready = !frame_done && (irow < HH) && (irow <= orow + R + 1);
    wire wr = in_valid && in_ready;
    wire [3:0] wbuf = irow % NB;

    // ------------------------------------------------------------------------------ read side
    reg signed [CW-1:0] t;                        // next column read index, -R .. W-1+R
    reg [CW-1:0] filled;                          // columns shifted into the window in this row
    reg issuing;                                  // reads of the current row still to issue
    wire [RW-1:0] need = (orow + R > HH - 1) ? HH - 1 : orow + R;
    wire rows_ready = (irow > need);
    wire stall = out_valid && !out_ready;
    wire go = !stall;
    wire issue = go && issuing && rows_ready && !frame_done;
    wire [AW-1:0] raddr = refl(t, W);

    // buffer of every window row for the current output row (registered with the read)
    reg [3:0] bsel [0:K-1];
    reg [3:0] rsel [0:K-1];
    integer a;
    always @(*)
        for (a = 0; a < K; a = a + 1) bsel[a] = refl(orow + a - R, HH) % NB;

    // the row buffers: one write port, one synchronous read port, read enable = go
    wire [PL*WD-1:0] rdata [0:NB-1];
    genvar b;
    generate
        for (b = 0; b < NB; b = b + 1) begin : rb
            reg [PL*WD-1:0] mem [0:W-1];
            reg [PL*WD-1:0] q;
            always @(posedge clk) begin
                if (wr && wbuf == b) mem[icol] <= in_pix;
                if (issue) q <= mem[raddr];
            end
            assign rdata[b] = q;
        end
    endgenerate

    reg rd_v, rd_last, rd_eof;
    reg [PL*WD-1:0] win [0:K-1][0:K-1];
    genvar gi, gj, gp;
    generate
        for (gi = 0; gi < K; gi = gi + 1) begin : wr_row
            for (gj = 0; gj < K; gj = gj + 1) begin : wr_col
                assign out_win[(gi*K + gj)*WD +: WD] = win[gi][gj][WD-1:0];
            end
        end
    endgenerate
    assign out_ctr = win[R][R];

    integer i, j;
    always @(posedge clk) begin
        if (rst) begin
            icol <= 0; irow <= 0; orow <= 0; frame_done <= 1'b0;
            t <= -R; filled <= 0; issuing <= 1'b1;
            rd_v <= 1'b0; rd_last <= 1'b0; rd_eof <= 1'b0;
            out_valid <= 1'b0; out_last <= 1'b0; out_eof <= 1'b0;
        end else begin
            // write side
            if (wr) begin
                if (icol == W - 1) begin icol <= 0; irow <= irow + 1'b1; end
                else icol <= icol + 1'b1;
            end
            if (go) begin
                // read issue
                rd_v <= issue;
                if (issue) begin
                    for (a = 0; a < K; a = a + 1) rsel[a] <= bsel[a];
                    rd_last <= (t == W - 1 + R);
                    rd_eof  <= (t == W - 1 + R) && (orow == HH - 1);
                    if (t == W - 1 + R) issuing <= 1'b0;
                    t <= t + 1'b1;
                end
                // shift the arriving column into the window
                out_valid <= 1'b0;
                if (rd_v) begin
                    for (i = 0; i < K; i = i + 1) begin
                        for (j = 0; j < K - 1; j = j + 1) win[i][j] <= win[i][j+1];
                        win[i][K-1] <= rdata[rsel[i]];
                    end
                    filled <= filled + 1'b1;
                    out_valid <= (filled >= K - 1);
                    out_last <= rd_last;
                    out_eof <= rd_eof;
                    if (rd_last) begin              // the row's last column is in: next output row
                        filled <= 0;
                        t <= -R;
                        issuing <= 1'b1;
                        if (orow == HH - 1) begin
                            frame_done <= 1'b1;
                        end else orow <= orow + 1'b1;
                    end
                end
            end
            // a frame ends when its last window has been accepted
            if (frame_done && !out_valid && !rd_v) begin
                frame_done <= 1'b0; irow <= 0; orow <= 0; icol <= 0;
            end
        end
    end
endmodule
