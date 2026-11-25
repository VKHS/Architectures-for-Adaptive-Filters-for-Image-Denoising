// Pipelined binary adder tree: N signed W-bit inputs, ceil(log2 N) register levels, advance on en.
// Nodes are kept in heap order: node i adds children 2i+1 and 2i+2; the last N2 slots are the leaves.
module adder_tree #(
    parameter N = 8, W = 48
)(
    input  wire clk, en,
    input  wire [N*W-1:0] in,
    output wire signed [W-1:0] out
);
    function integer clog2;
        input integer v;
        integer t;
        begin
            clog2 = 0;
            for (t = v - 1; t > 0; t = t >> 1) clog2 = clog2 + 1;
        end
    endfunction
    localparam T  = clog2(N);
    localparam N2 = 1 << T;

    genvar i;
    generate
        if (N2 == 1) begin : g_one
            assign out = in[W-1:0];
        end else begin : g_tree
            reg  signed [W-1:0] nd [0:N2-2];
            wire signed [W-1:0] all [0:2*N2-2];
            for (i = 0; i < N2 - 1; i = i + 1) begin : g_int
                assign all[i] = nd[i];
            end
            for (i = 0; i < N2; i = i + 1) begin : g_leaf
                if (i < N) begin : g_in
                    assign all[N2 - 1 + i] = in[i*W +: W];
                end else begin : g_pad
                    assign all[N2 - 1 + i] = {W{1'b0}};
                end
            end
            integer j;
            always @(posedge clk)
                if (en)
                    for (j = 0; j < N2 - 1; j = j + 1)
                        nd[j] <= all[2*j + 1] + all[2*j + 2];
            assign out = nd[0];
        end
    endgenerate
endmodule
