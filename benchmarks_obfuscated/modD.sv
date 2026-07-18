module modD (
    input wire clk,
    input wire rst,
    input wire i0,
    input wire i1
);
    localparam P0    = 3;
    localparam P1 = 1 << P0;

    reg [P0:0] ptrX, ptrY;

    wire w0 = (ptrX == ptrY);
    wire w1  = (ptrX == {~ptrY[P0], ptrY[P0-1:0]});

    wire e0 = i0 && !w1;
    wire e1  = i1  && !w0;

    always @(posedge clk) begin
        if (rst) begin
            ptrX <= 0;
            ptrY <= 0;
        end else begin
            ptrX <= ptrX + e0;
            ptrY <= ptrY + e1;
        end
    end

`ifdef FORMAL
    reg f_past_valid;
    initial f_past_valid = 1'b0;
    always @(posedge clk) f_past_valid <= 1'b1;

    initial assume (rst);

    reg [P0:0] ghost0;
    always @(posedge clk) begin
        if (rst)
            ghost0 <= 0;
        else
            ghost0 <= ghost0 + e0 - e1;
    end

    always @(posedge clk) if (f_past_valid) begin
        assert (ghost0 <= P1);
        assert (w0 == (ghost0 == 0));
        assert (w1  == (ghost0 == P1));
    end

    // %INVARIANTS%
`endif
endmodule
