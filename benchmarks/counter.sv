// Saturating counter. The safety property is inductive on its own —
// this benchmark is the sanity check that the flow proves something without help.
module counter (
    input wire clk,
    input wire rst,
    input wire en
);
    localparam [7:0] MAX = 8'd200;

    reg [7:0] cnt;

    always @(posedge clk) begin
        if (rst)
            cnt <= 8'd0;
        else if (en && cnt < MAX)
            cnt <= cnt + 8'd1;
    end

`ifdef FORMAL
    reg f_past_valid;
    initial f_past_valid = 1'b0;
    always @(posedge clk) f_past_valid <= 1'b1;

    initial assume (rst);

    always @(posedge clk) if (f_past_valid) begin
        assert (cnt <= MAX);
    end

    // %INVARIANTS%
`endif
endmodule
