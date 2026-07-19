// Real production RTL, verbatim from BaseJump STL (bsg_dataflow/bsg_fifo_tracker.sv
// + bsg_misc/bsg_circular_ptr.sv, bespoke-silicon-group/basejump_stl, Solderpad
// Hardware License 2.1) -- the pointer/full/empty tracking logic used inside real
// FIFOs in real chips. els_p/slots_p fixed at 6 (deliberately non-power-of-2, to
// exercise the interesting wraparound-arithmetic branch of bsg_circular_ptr, not
// the trivial power-of-2 shortcut). Only changes from upstream: `BSG_INV_PARAM
// macros resolved to concrete values, and the two `BSG_* helper macros actually
// used are inlined below instead of pulling in the full bsg_defines.sv header.
// The FORMAL block is ours, not upstream's.

`define BSG_SAFE_CLOG2(x) ( (((x)==1) || ((x)==0))? 1 : $clog2((x)))
`define BSG_IS_POW2(x) ( (1 << $clog2(x)) == (x))

module bsg_circular_ptr #(parameter slots_p = 6
                          , parameter max_add_p = 1
                          , parameter const_incr_p = 1'b0
                          , parameter ptr_width_lp = `BSG_SAFE_CLOG2(slots_p)
                          )
   (input clk
   , input reset_i
   , input [$clog2(max_add_p+1)-1:0] add_i
   , output [ptr_width_lp-1:0] o
   , output [ptr_width_lp-1:0] n_o
   );

   logic [ptr_width_lp-1:0] ptr_r, ptr_n, ptr_nowrap;
   logic [ptr_width_lp:0] ptr_wrap;

   assign o = ptr_r;
   assign n_o = ptr_n;

   always_ff @(posedge clk)
     if (reset_i) ptr_r <= '0;
     else ptr_r <= ptr_n;

   if (slots_p == 1)
     begin
        assign ptr_n = 1'b0;
        wire ignore = |add_i;
     end
   else

   if (`BSG_IS_POW2(slots_p))
     begin
        if ((max_add_p == 1) || const_incr_p)
          begin
             wire [ptr_width_lp-1:0] ptr_r_p1 = ptr_r + max_add_p[ptr_width_lp-1:0];
             assign ptr_n = add_i ? ptr_r_p1 : ptr_r;
          end
        else
          assign ptr_n = ptr_width_lp ' (ptr_r + add_i);
     end
   else
     begin: notpow2
        assign ptr_wrap = (ptr_width_lp+1)'({ 1'b0, ptr_r } - slots_p + add_i);
        assign ptr_nowrap = ptr_r + add_i;
        assign ptr_n = ~ptr_wrap[ptr_width_lp] ? ptr_wrap[0+:ptr_width_lp] : ptr_nowrap;
     end
endmodule

module bsg_fifo_tracker #(parameter els_p = 6
                          , parameter ptr_width_lp = `BSG_SAFE_CLOG2(els_p)
                          )
   (input clk_i
   , input reset_i

   , input enq_i
   , input deq_i

   , output [ptr_width_lp-1:0] wptr_r_o
   , output [ptr_width_lp-1:0] rptr_r_o
   , output [ptr_width_lp-1:0] rptr_n_o

   , output full_o
   , output empty_o
   );

   logic [ptr_width_lp-1:0] rptr_r, rptr_n, wptr_r;

   assign wptr_r_o = wptr_r;
   assign rptr_r_o = rptr_r;
   assign rptr_n_o = rptr_n;

   logic enq_r, deq_r;
   logic empty, full, equal_ptrs;

   bsg_circular_ptr #(.slots_p (els_p)
                      ,.max_add_p(1 )
                      ) rptr
     ( .clk     (clk_i  )
     , .reset_i (reset_i)
     , .add_i   (deq_i  )
     , .o       (rptr_r )
     , .n_o     (rptr_n)
     );

   bsg_circular_ptr #(.slots_p (els_p)
                      ,.max_add_p(1 )
                      ) wptr
     ( .clk     (clk_i  )
     , .reset_i (reset_i)
     , .add_i   (enq_i  )
     , .o       (wptr_r )
     , .n_o     ()
     );

   always_ff @(posedge clk_i)
     if (reset_i)
       begin
          enq_r <= 1'b0;
          deq_r <= 1'b1;
       end
     else
       begin
          if (enq_i | deq_i)
            begin
               enq_r <= enq_i;
               deq_r <= deq_i;
            end
       end

   assign equal_ptrs = (rptr_r == wptr_r);
   assign empty = equal_ptrs & deq_r;
   assign full = equal_ptrs & enq_r;

   assign full_o = full;
   assign empty_o = empty;

`ifdef FORMAL
    reg f_past_valid;
    initial f_past_valid = 1'b0;
    always @(posedge clk_i) f_past_valid <= 1'b1;

    initial assume (reset_i);

    // Realistic caller contract, matching how this tracker is actually used
    // inside bsg_fifo_1r1w_small_unhardened upstream: enq is only ever
    // asserted when not full, deq only when not empty. The tracker was never
    // designed to be driven by an unconstrained adversarial environment.
    always @(posedge clk_i) begin
        assume (!(enq_i && full_o));
        assume (!(deq_i && empty_o));
    end

    always @(posedge clk_i) if (f_past_valid) begin
        assert (!(full_o && empty_o));
    end

    // %INVARIANTS%
`endif
endmodule
