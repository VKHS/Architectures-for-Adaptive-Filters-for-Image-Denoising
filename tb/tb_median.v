`timescale 1ns/1ps
// Testbench of median3x3_top: streams an image (hex file of Q12 codes) with random idle cycles, logs every output.
module tb_median;
    parameter W = 32, HH = 24, SWITCH = 0, THR = 410, IDLE_PROB = 10;
    parameter IMG = "img.hex", LOG = "log.txt";
    localparam N = W * HH;

    reg clk = 1'b0;
    always #5 clk = ~clk;
    reg rst = 1'b1;
    reg in_valid = 1'b0;
    reg signed [15:0] in_pix = 0;
    wire in_ready, out_valid, out_flag;
    wire signed [15:0] out_pix;

    median3x3_top #(.W(W), .HH(HH), .SWITCH(SWITCH), .THR(THR)) dut (
        .clk(clk), .rst(rst), .in_valid(in_valid), .in_ready(in_ready), .in_pix(in_pix),
        .out_valid(out_valid), .out_pix(out_pix), .out_flag(out_flag));

    reg [15:0] img [0:N-1];
    integer fo, k, nout = 0, cyc = 0, seed = 11;
    always @(posedge clk) cyc <= cyc + 1;
    always @(negedge clk)
        if (!rst && out_valid) begin
            $fwrite(fo, "O %0d %0d\n", out_pix, out_flag);
            nout = nout + 1;
        end

    initial begin
        $readmemh(IMG, img);
        fo = $fopen(LOG, "w");
        repeat (4) @(posedge clk);
        @(negedge clk) rst = 1'b0;
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
        while (nout < N) @(posedge clk);
        repeat (20) @(posedge clk);
        $display("tb_median: %0d outputs in %0d cycles", nout, cyc);
        $fclose(fo);
        $finish;
    end
endmodule
