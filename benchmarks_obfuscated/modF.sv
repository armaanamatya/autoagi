module modF (
    input wire clk,
    input wire rst,
    input wire i0,
    input wire i1,
    input wire [3:0] i2,
    input wire [3:0] i3
);
    reg [7:0] r0;
    reg [7:0] r1;
    reg [3:0] r2;
    reg [3:0] r3, r4;
    reg s0, s1;

    always @(posedge clk) begin
        if (rst) begin
            s0 <= 0;
            s1 <= 0;
        end else if (i0 && !s0) begin
            r0 <= 0;
            r1  <= {4'b0, i2};
            r2 <= i3;
            r3    <= i2;
            r4    <= i3;
            s0  <= 1;
            s1  <= 0;
        end else if (s0 && !i1) begin
            if (r2 == 0) begin
                s0 <= 0;
                s1 <= 1;
            end else begin
                if (r2[0])
                    r0 <= r0 + r1;
                r1  <= r1 << 1;
                r2 <= r2 >> 1;
            end
        end
    end

`ifdef FORMAL
    reg f_past_valid;
    initial f_past_valid = 1'b0;
    always @(posedge clk) f_past_valid <= 1'b1;

    initial assume (rst);

    always @(posedge clk) if (f_past_valid) begin
        if (s1)
            assert (r0 == r3 * r4);
    end

    // %INVARIANTS%
`endif
endmodule
