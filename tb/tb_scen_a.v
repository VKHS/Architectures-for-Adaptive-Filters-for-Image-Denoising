`timescale 1ns/1ps
// Testbench of scen_a_top: streams an image (hex file of Q12 codes, raster order) PASSES times with random idle
// cycles and logs every output pixel.
module tb_scen_a;
    parameter W = 32, HH = 24, K = 2, ENGINE = 0, P = 2, S = 12;
    parameter [127:0] UINC = 0, VINC = 0;
    parameter DRAIN_ROW = 0, DRAIN_FRAME = 64, IDLE_PROB = 10, PASSES = 2, OFF = 2048;
    parameter IMG = "img.hex", LOG = "log.txt", COS_FILE = "cos.hex";
    localparam N = W * HH;

    reg clk = 1'b0;
    always #5 clk = ~clk;
    reg rst = 1'b1;
    reg in_valid = 1'b0;
    reg signed [15:0] in_pix = 0;
    wire in_ready, out_valid;
    wire signed [15:0] out_pix;

    scen_a_top #(.W(W), .HH(HH), .K(K), .ENGINE(ENGINE), .P(P), .S(S), .UINC(UINC[K*32-1:0]),
                 .VINC(VINC[K*32-1:0]), .COS_FILE(COS_FILE), .DRAIN_ROW(DRAIN_ROW), .DRAIN_FRAME(DRAIN_FRAME)) dut (
        .clk(clk), .rst(rst), .in_valid(in_valid), .in_ready(in_ready), .in_pix(in_pix), .off(OFF[15:0]),
        .out_valid(out_valid), .out_pix(out_pix));

    reg [15:0] img [0:N-1];
    integer fo, k, p, nout = 0, cyc = 0, seed = 11;
    always @(posedge clk) cyc <= cyc + 1;
    always @(negedge clk)
        if (!rst && out_valid) begin
            $fwrite(fo, "O %0d 0\n", out_pix);
            nout = nout + 1;
        end

    initial begin
        $readmemh(IMG, img);
        fo = $fopen(LOG, "w");
        repeat (4) @(posedge clk);
        @(negedge clk) rst = 1'b0;
        for (p = 0; p < PASSES; p = p + 1)
            for (k = 0; k < N; k = k + 1) begin
                @(negedge clk);
                while (($random(seed) & 255) < IDLE_PROB * 256 / 100) begin
                    in_valid = 1'b0;
                    @(negedge clk);
                end
                in_valid = 1'b1;
                in_pix = img[k];
                while (!in_ready) @(negedge clk);
                @(posedge clk);
            end
        @(negedge clk) in_valid = 1'b0;
        while (nout < PASSES * N) @(posedge clk);
        repeat (20) @(posedge clk);
        $display("tb_scen_a: %0d outputs in %0d cycles", nout, cyc);
        $fclose(fo);
        $finish;
    end
endmodule
