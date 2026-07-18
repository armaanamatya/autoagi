// Shift-add multiplier, 4x4 -> 8 bit. The classic invariant-synthesis
// challenge: the end-to-end property "when done, acc == a0 * b0" says nothing
// about the machine mid-flight, so induction fails from any bogus mid-state.
// The strengthening invariant the hunter must find is the algorithm's loop
// invariant relating five registers:
//   busy -> acc + a_sh * b_rem == a0 * b0
module mult (
    input wire clk,
    input wire rst,
    input wire start,
    input wire stall,   // backpressure: hold state while busy
    input wire [3:0] a_in,
    input wire [3:0] b_in
);
    reg [7:0] acc;    // accumulated partial product
    reg [7:0] a_sh;   // a, shifted left each step
    reg [3:0] b_rem;  // remaining bits of b
    reg [3:0] a0, b0; // operands latched at start (for the spec)
    reg busy, done;

    always @(posedge clk) begin
        if (rst) begin
            busy <= 0;
            done <= 0;
        end else if (start && !busy) begin
            acc   <= 0;
            a_sh  <= {4'b0, a_in};
            b_rem <= b_in;
            a0    <= a_in;
            b0    <= b_in;
            busy  <= 1;
            done  <= 0;
        end else if (busy && !stall) begin
            if (b_rem == 0) begin
                busy <= 0;
                done <= 1;
            end else begin
                if (b_rem[0])
                    acc <= acc + a_sh;
                a_sh  <= a_sh << 1;
                b_rem <= b_rem >> 1;
            end
        end
    end

`ifdef FORMAL
    reg f_past_valid;
    initial f_past_valid = 1'b0;
    always @(posedge clk) f_past_valid <= 1'b1;

    initial assume (rst);

    always @(posedge clk) if (f_past_valid) begin
        if (done)
            assert (acc == a0 * b0);
    end

    // %INVARIANTS%
`endif
endmodule
