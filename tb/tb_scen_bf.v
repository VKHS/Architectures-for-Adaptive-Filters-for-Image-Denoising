`timescale 1ns/1ps
// Testbench of scen_b_top (TOP = 0) and scen_f_top (TOP = 1). Replays a step file written by
// sim/test_scenarios.py, one line per pixel:  mode flush pix ref  (flush = 1: a frame end, no pixel).
module tb_scen_bf;
    parameter TOP = 0;
    parameter W = 32, S = 6, MODE = 0, SK = 0, TAU = 328;                          // B
    parameter NOB = 16, LOGNOB = 4, XSEL = 0, ENGINE = 0, DRAIN_ROW = 0;          // F
    parameter IDLE_PROB = 10;
    parameter STIM = "stim.txt", LOG = "log.txt";

    reg clk = 1'b0;
    always #5 clk = ~clk;
    reg rst = 1'b1;
    reg in_valid = 1'b0, in_flush = 1'b0;
    reg [1:0] mode = 0;
    reg signed [15:0] in_pix = 0, in_ref = 0;
    wire in_ready, out_valid;
    wire signed [15:0] out_pix, out_bias;

    generate
        if (TOP == 0) begin : u
            scen_b_top #(.W(W), .S(S), .MODE(MODE), .SK(SK), .TAU(TAU)) dut (
                .clk(clk), .rst(rst), .in_valid(in_valid), .in_ready(in_ready), .in_pix(in_pix),
                .out_valid(out_valid), .out_pix(out_pix), .out_bias(out_bias));
        end else begin : u
            scen_f_top #(.W(W), .NOB(NOB), .LOGNOB(LOGNOB), .XSEL(XSEL), .ENGINE(ENGINE), .S(S),
                         .DRAIN_ROW(DRAIN_ROW)) dut (
                .clk(clk), .rst(rst), .mode(mode), .in_valid(in_valid), .in_ready(in_ready), .in_pix(in_pix),
                .in_ref(in_ref), .in_flush(in_flush), .out_valid(out_valid), .out_pix(out_pix));
            assign out_bias = 0;
        end
    endgenerate

    integer fi, fo, r, nout = 0, seed = 5;
    integer vm, vf, vp, vr;
    always @(negedge clk)
        if (!rst && out_valid) begin
            $fwrite(fo, "O %0d %0d\n", out_pix, out_bias);
            nout = nout + 1;
        end

    initial begin
        fi = $fopen(STIM, "r");
        fo = $fopen(LOG, "w");
        repeat (4) @(posedge clk);
        @(negedge clk) rst = 1'b0;
        while (!$feof(fi)) begin
            r = $fscanf(fi, "%d %d %d %d\n", vm, vf, vp, vr);
            if (r == 4) begin
                @(negedge clk);
                while (($random(seed) & 255) < IDLE_PROB * 256 / 100) begin
                    in_valid = 1'b0;
                    @(negedge clk);
                end
                mode = vm;
                if (vf) begin
                    in_valid = 1'b0; in_flush = 1'b1;
                    @(negedge clk) in_flush = 1'b0;
                    repeat (80) @(negedge clk);
                end else begin
                    in_valid = 1'b1; in_pix = vp; in_ref = vr;
                    while (!in_ready) @(negedge clk);
                    @(posedge clk);
                end
            end
        end
        @(negedge clk) in_valid = 1'b0;
        repeat (200) @(posedge clk);
        $display("tb_scen_bf: %0d outputs", nout);
        $fclose(fo);
        $finish;
    end
endmodule
