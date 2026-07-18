module modC (
    input wire clk,
    input wire rst,
    input wire [3:0] i0
);
    reg  [3:0] r0;
    wire [3:0] w0 = i0 & r0;

    always @(posedge clk) begin
        if (rst)
            r0 <= 4'b0001;
        else
            r0 <= {r0[2:0], r0[3]};
    end

`ifdef FORMAL
    reg f_past_valid;
    initial f_past_valid = 1'b0;
    always @(posedge clk) f_past_valid <= 1'b1;

    initial assume (rst);

    always @(posedge clk) if (f_past_valid) begin
        assert (!(w0[0] && w0[1]));
        assert (!(w0[1] && w0[2]));
        assert (!(w0[2] && w0[3]));
        assert (!(w0[0] && w0[2]));
        assert (!(w0[0] && w0[3]));
        assert (!(w0[1] && w0[3]));
    end

    // %INVARIANTS%
`endif
endmodule
