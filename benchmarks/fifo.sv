// Classic pointer-based FIFO: full/empty computed purely from the pointers
// (with a wrap bit), plus a ghost occupancy counter in the formal block.
// The assertions relating the ghost counter to full/empty are not inductive
// on their own — the induction step can pick unrelated wptr/rptr/f_count.
// The strengthening invariant the hunter must find is
//   f_count == wptr - rptr
module fifo (
    input wire clk,
    input wire rst,
    input wire push,
    input wire pop
);
    localparam AW    = 3;
    localparam DEPTH = 1 << AW;  // 8

    reg [AW:0] wptr, rptr;       // one extra wrap bit

    wire empty = (wptr == rptr);
    wire full  = (wptr == {~rptr[AW], rptr[AW-1:0]});

    wire do_push = push && !full;
    wire do_pop  = pop  && !empty;

    always @(posedge clk) begin
        if (rst) begin
            wptr <= 0;
            rptr <= 0;
        end else begin
            wptr <= wptr + do_push;
            rptr <= rptr + do_pop;
        end
    end

`ifdef FORMAL
    reg f_past_valid;
    initial f_past_valid = 1'b0;
    always @(posedge clk) f_past_valid <= 1'b1;

    initial assume (rst);

    // ghost occupancy counter
    reg [AW:0] f_count;
    always @(posedge clk) begin
        if (rst)
            f_count <= 0;
        else
            f_count <= f_count + do_push - do_pop;
    end

    always @(posedge clk) if (f_past_valid) begin
        assert (f_count <= DEPTH);
        assert (empty == (f_count == 0));
        assert (full  == (f_count == DEPTH));
    end

    // %INVARIANTS%
`endif
endmodule
