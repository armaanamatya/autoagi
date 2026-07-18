// Counter that steps by 2 from 0 (mod 256). The property "cnt != 5" is true
// (cnt is always even) but NOT inductive: assuming only cnt != 5, the solver can
// place cnt = 3 in the induction step and reach 5. The strengthening invariant
// the hunter must find is that cnt stays even (cnt[0] == 1'b0).
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
