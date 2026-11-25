`timescale 1ns/1ps
// Generic engine testbench. Replays a step file written by sim/test_engines.py and logs every output, every
// accepted sample and its clock cycle; the Python side compares the log with the bit-accurate model.
//
// Step file, one line per step:   valid shift drain adapt last d p x(hex, L*WD bits, tap 0 in the LSBs)
//   valid = 1 : a sample; it is held until the engine accepts it (handshake engines wait, pipelined ones take it)
//   valid = 0 : one cycle without a sample; shift / drain request a pre-roll shift or a drain step
// Log lines:  I <cycle>                       a sample was accepted at this clock edge
//             O <cycle> <o> <y> <e> <flag>    an output
module tb_engine;
    parameter ENGINE = 0;               // 0 serial, 1 folded, 2 df, 3 systolic, 4 rowblock, 5 da
    parameter L = 4, P = 2, TDL = 0;
    parameter WD = 16, FD = 12, WW = 24, FW = 20, WA = 48, S = 7, RULE = 0, LEAK = 0;
    parameter OUT = 0, GATED = 0;
    parameter [WA-1:0] A0 = 0;
    parameter TAIL = 400;
    parameter STIM = "stim.txt", LOG = "log.txt";

    reg clk = 1'b0;
    always #5 clk = ~clk;
    reg rst = 1'b1;
    reg in_valid = 1'b0, in_shift = 1'b0, in_drain = 1'b0, in_adapt = 1'b0, in_last = 1'b0;
    reg [L*WD-1:0] in_x = 0;
    reg signed [WD-1:0] in_d = 0, in_p = 0;
    wire in_ready, out_valid, out_flag;
    wire signed [WD-1:0] out_o, out_y, out_e;

    lms_engine #(.ENGINE(ENGINE), .L(L), .P(P), .TDL(TDL), .WD(WD), .FD(FD), .WW(WW), .FW(FW), .WA(WA), .S(S),
                 .RULE(RULE), .LEAK(LEAK), .OUT(OUT), .GATED(GATED), .A0(A0)) dut (
        .clk(clk), .rst(rst), .in_valid(in_valid), .in_shift(in_shift), .in_drain(in_drain), .in_ready(in_ready),
        .in_x(in_x), .in_d(in_d), .in_p(in_p), .in_adapt(in_adapt), .in_last(in_last), .out_valid(out_valid),
        .out_o(out_o), .out_y(out_y), .out_e(out_e), .out_flag(out_flag));

    integer cyc = 0;
    always @(posedge clk) cyc <= cyc + 1;

    integer fi, fo, r, nin = 0, nout = 0;
    integer v, s, dr, a, l, dv, pv;
    reg [L*WD-1:0] xv;

    always @(negedge clk)
        if (!rst && out_valid) begin
            $fwrite(fo, "O %0d %0d %0d %0d %0d\n", cyc, out_o, out_y, out_e, out_flag);
            nout = nout + 1;
        end

    initial begin
        fi = $fopen(STIM, "r");
        fo = $fopen(LOG, "w");
        if (fi == 0) begin $display("cannot open %0s", STIM); $finish; end
        repeat (4) @(posedge clk);
        @(negedge clk) rst = 1'b0;
        while (!$feof(fi)) begin
            r = $fscanf(fi, "%d %d %d %d %d %d %d %h\n", v, s, dr, a, l, dv, pv, xv);
            if (r == 8) begin
                @(negedge clk);
                in_valid = v; in_shift = s; in_drain = dr; in_adapt = a; in_last = l;
                in_d = dv; in_p = pv; in_x = xv;
                if (v) begin
                    while (!in_ready) @(negedge clk);
                    $fwrite(fo, "I %0d\n", cyc);
                    nin = nin + 1;
                end
                @(posedge clk);
            end
        end
        @(negedge clk);
        in_valid = 1'b0; in_shift = 1'b0; in_drain = 1'b0; in_last = 1'b0;
        repeat (TAIL) @(posedge clk);
        $display("tb_engine: %0d samples in, %0d outputs", nin, nout);
        $fclose(fo);
        $finish;
    end
endmodule
