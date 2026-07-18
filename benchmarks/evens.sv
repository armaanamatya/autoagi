// Counter that steps by 2 from 0 (mod 256). The safety property below is true
// but not inductive on its own — closing the proof requires strengthening.
module evens (
    input wire clk,
    input wire rst,
    input wire en
);
    reg [7:0] cnt;

    always @(posedge clk) begin
        if (rst)
            cnt <= 8'd0;
        else if (en)
            cnt <= cnt + 8'd2;
    end

`ifdef FORMAL
    reg f_past_valid;
    initial f_past_valid = 1'b0;
    always @(posedge clk) f_past_valid <= 1'b1;

    initial assume (rst);

    always @(posedge clk) if (f_past_valid) begin
        assert (cnt != 8'd5);
    end

    // %INVARIANTS%
`endif
endmodule
