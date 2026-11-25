`timescale 1ns/1ps
// Testbench of scen_de_top: streams an image (hex file of Q12 codes, raster order) PASSES times; in the gated
// mode the taps of a later pass come from the previous pass's output, as in the software. Logs every output.
module tb_scen_de;
    parameter W = 32, HH = 24, R = 2, HOLE = 0, ENGINE = 0, P = 2;
    parameter S = 8, RULE = 0, GATED = 0;
    parameter [47:0] A0 = 0;
    parameter DRAIN_ROW = 0, DRAIN_FRAME = 64, PASSES = 2, OFF = 2048, IDLE_PROB = 10;
    parameter IMG = "img.hex", LOG = "log.txt";
    localparam N = W * HH;

    reg clk = 1'b0;
    always #5 clk = ~clk;
    reg rst = 1'b1;
    reg in_valid = 1'b0;
    reg signed [15:0] in_tap = 0, in_d = 0;
    wire in_ready, out_valid, out_flag;
    wire signed [15:0] out_pix;

    scen_de_top #(.W(W), .HH(HH), .R(R), .HOLE(HOLE), .ENGINE(ENGINE), .P(P), .S(S), .RULE(RULE),
                  .GATED(GATED), .A0(A0), .DRAIN_ROW(DRAIN_ROW), .DRAIN_FRAME(DRAIN_FRAME)) dut (
        .clk(clk), .rst(rst), .in_valid(in_valid), .in_ready(in_ready), .in_tap(in_tap), .in_d(in_d),
        .off(OFF[15:0]), .out_valid(out_valid), .out_pix(out_pix), .out_flag(out_flag));

    reg [15:0] img  [0:N-1];
    reg [15:0] prev [0:N-1];
    reg [15:0] cur  [0:N-1];
    integer fo, k, p, nout = 0, cyc = 0, seed = 7;
    always @(posedge clk) cyc <= cyc + 1;

    always @(negedge clk)
        if (!rst && out_valid) begin
            $fwrite(fo, "O %0d %0d\n", out_pix, out_flag);
            cur[nout % N] = out_pix;
            nout = nout + 1;
        end

    initial begin
        $readmemh(IMG, img);
        fo = $fopen(LOG, "w");
        repeat (4) @(posedge clk);
        @(negedge clk) rst = 1'b0;
        for (p = 0; p < PASSES; p = p + 1) begin
            for (k = 0; k < N; k = k + 1) begin
                @(negedge clk);
                // random idle cycles between pixels (the generator and the engines must not care)
                while (($random(seed) & 255) < IDLE_PROB * 256 / 100) begin
                    in_valid = 1'b0;
                    @(negedge clk);
                end
                in_valid = 1'b1;
                in_tap = (GATED != 0 && p > 0) ? prev[k] : img[k];
                in_d = img[k];
                while (!in_ready) @(negedge clk);
                @(posedge clk);
            end
            @(negedge clk) in_valid = 1'b0;
            while (nout < (p + 1) * N) @(posedge clk);
            for (k = 0; k < N; k = k + 1) prev[k] = cur[k];
        end
        repeat (20) @(posedge clk);
        $display("tb_scen_de: %0d outputs in %0d cycles", nout, cyc);
        $fclose(fo);
        $finish;
    end
endmodule
