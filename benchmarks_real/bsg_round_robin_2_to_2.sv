// Real production RTL, verbatim from BaseJump STL (bsg_dataflow/bsg_round_robin_2_to_2.sv,
// bespoke-silicon-group/basejump_stl, Solderpad Hardware License 2.1) -- round-robins
// a pair of parallel elements onto a pair of FIFOs. Only change from upstream: the
// `BSG_INV_PARAM macro resolved to a concrete width_p=4. The FORMAL block is ours,
// not upstream's.

module bsg_round_robin_2_to_2 #(parameter width_p = 4)
   (input clk_i
   , input reset_i
   , input [width_p*2-1:0] data_i
   , input [1:0] v_i
   , output [1:0] ready_o

   , output [width_p*2-1:0] data_o
   , output [1:0] v_o
   , input [1:0] ready_i
   );

   logic head_r;

   always_ff @(posedge clk_i)
     if (reset_i)
       head_r <= 0;
     else
       head_r <= ^ {head_r, v_i & ready_o};

   assign data_o = head_r ? { data_i[0+:width_p], data_i[width_p+:width_p] } : data_i;
   assign v_o = head_r ? { v_i[0], v_i[1] } : v_i;
   assign ready_o = head_r ? { ready_i[0], ready_i[1] } : ready_i;

`ifdef FORMAL
    reg f_past_valid;
    initial f_past_valid = 1'b0;
    always @(posedge clk_i) f_past_valid <= 1'b1;

    initial assume (reset_i);

    // the swizzle must be a permutation of its input: identity or exact swap,
    // never anything else (no lost/duplicated/fabricated lane).
    always @(posedge clk_i) if (f_past_valid) begin
        assert ((v_o == v_i) || (v_o == {v_i[0], v_i[1]}));
    end

    // %INVARIANTS%
`endif
endmodule
