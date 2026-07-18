// Rotating token arbiter. The mutual-exclusion property below is true but not
// inductive on its own — closing the proof requires strengthening.
module token_ring (
    input wire clk,
    input wire rst,
    input wire [3:0] req
);
    reg  [3:0] token;
    wire [3:0] gnt = req & token;

    always @(posedge clk) begin
        if (rst)
            token <= 4'b0001;
        else
            token <= {token[2:0], token[3]};  // rotate left
    end

`ifdef FORMAL
    reg f_past_valid;
    initial f_past_valid = 1'b0;
    always @(posedge clk) f_past_valid <= 1'b1;

    initial assume (rst);

    always @(posedge clk) if (f_past_valid) begin
        // at most one grant active
        assert (!(gnt[0] && gnt[1]));
        assert (!(gnt[1] && gnt[2]));
        assert (!(gnt[2] && gnt[3]));
        assert (!(gnt[0] && gnt[2]));
        assert (!(gnt[0] && gnt[3]));
        assert (!(gnt[1] && gnt[3]));
    end

    // %INVARIANTS%
`endif
endmodule
