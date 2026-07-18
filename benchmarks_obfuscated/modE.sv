module modE (
    input wire clk,
    input wire rst,
    input wire i0,
    input wire i1,
    input wire i2
);
    localparam P0 = 8;

    reg [3:0] resX;
    reg [3:0] resY;
    reg [3:0] resZ;

    wire e0 = i0 && (resX != 0);
    wire e1 = i1 && (resY != 0);
    wire e2 = i2 && (resZ != 0);

    always @(posedge clk) begin
        if (rst) begin
            resX <= P0;
            resY <= 0;
            resZ <= 0;
        end else begin
            resX <= resX - e0 + e2;
            resY <= resY + e0 - e1;
            resZ <= resZ + e1 - e2;
        end
    end

`ifdef FORMAL
    reg f_past_valid;
    initial f_past_valid = 1'b0;
    always @(posedge clk) f_past_valid <= 1'b1;

    initial assume (rst);

    always @(posedge clk) if (f_past_valid) begin
        assert (resZ  <= P0);
        assert (resX <= P0);
    end

    // %INVARIANTS%
`endif
endmodule
