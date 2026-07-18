module modA (
    input wire clk,
    input wire rst,
    input wire i0
);
    localparam [7:0] P0 = 8'd200;

    reg [7:0] r0;

    always @(posedge clk) begin
        if (rst)
            r0 <= 8'd0;
        else if (i0 && r0 < P0)
            r0 <= r0 + 8'd1;
    end

`ifdef FORMAL
    reg f_past_valid;
    initial f_past_valid = 1'b0;
    always @(posedge clk) f_past_valid <= 1'b1;

    initial assume (rst);

    always @(posedge clk) if (f_past_valid) begin
        assert (r0 <= P0);
    end

    // %INVARIANTS%
`endif
endmodule
