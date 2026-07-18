// Credit-based flow control (the mechanism behind NoC / PCIe / AXI credit
// systems). Three coupled counters: sender credits, packets in flight, receiver
// buffer occupancy. The safety property "the receiver buffer never overflows"
// is true but not inductive: the induction step can start from occ=8 with
// in_flight=1 and push one more packet in. The strengthening invariant the
// hunter must find is the conservation law
//   credits + in_flight + occ == TOTAL
module credits (
    input wire clk,
    input wire rst,
    input wire send,    // sender emits a packet (if it has a credit)
    input wire arrive,  // a packet in flight reaches the receiver
    input wire free     // receiver frees a buffer slot, returning a credit
);
    localparam TOTAL = 8;

    reg [3:0] credits;    // credits held by the sender
    reg [3:0] in_flight;  // packets on the wire
    reg [3:0] occ;        // occupied receiver buffer slots

    wire do_send   = send   && (credits  != 0);
    wire do_arrive = arrive && (in_flight != 0);
    wire do_free   = free   && (occ      != 0);

    always @(posedge clk) begin
        if (rst) begin
            credits   <= TOTAL;
            in_flight <= 0;
            occ       <= 0;
        end else begin
            credits   <= credits   - do_send   + do_free;
            in_flight <= in_flight + do_send   - do_arrive;
            occ       <= occ       + do_arrive - do_free;
        end
    end

`ifdef FORMAL
    reg f_past_valid;
    initial f_past_valid = 1'b0;
    always @(posedge clk) f_past_valid <= 1'b1;

    initial assume (rst);

    always @(posedge clk) if (f_past_valid) begin
        assert (occ     <= TOTAL);  // buffer never overflows
        assert (credits <= TOTAL);  // credits never exceed the pool
    end

    // %INVARIANTS%
`endif
endmodule
