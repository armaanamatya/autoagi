// Shift-add multiplier, 16x16 -> 32 bit, with stall (backpressure). Same
// structure as mult.sv at a width where bit-level model checking struggles.
// The end-to-end property is true but not inductive on its own — closing the
// proof requires strengthening.
module mult16 (
    input wire clk,
    input wire rst,
    input wire start,
    input wire stall,
    input wire [15:0] a_in,
    input wire [15:0] b_in
);
    reg [31:0] acc;
    reg [31:0] a_sh;
    reg [15:0] b_rem;
    reg [15:0] a0, b0;
    reg busy, done;

    always @(posedge clk) begin
        if (rst) begin
            busy <= 0;
            done <= 0;
        end else if (start && !busy) begin
            acc   <= 0;
            a_sh  <= {16'b0, a_in};
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
