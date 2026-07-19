// Real production RTL, verbatim from BaseJump STL (bsg_misc/bsg_counter_up_down.sv,
// bespoke-silicon-group/basejump_stl, Solderpad Hardware License 2.1), used in real
// silicon (e.g. credit counters between chips). Only changes from upstream: the
// `BSG_INV_PARAM / `BSG_WIDTH macros (tool-portable "no default" / width-compute
// helpers) resolved to concrete values -- max_val_p=10, init_val_p=0, max_step_p=1,
// so step_width_lp=1, ptr_width_lp=4 -- so the module elaborates standalone with no
// macro header dependency. The FORMAL block below is ours, not upstream's.

module bsg_counter_up_down #( parameter max_val_p = 10
                             , parameter init_val_p = 0
                             , parameter max_step_p = 1
                             , parameter step_width_lp = 1  // BSG_WIDTH(max_step_p)
                             , parameter ptr_width_lp   = 4  // BSG_WIDTH(max_val_p)
                             )
   ( input clk_i
   , input reset_i

   , input [step_width_lp-1:0] up_i
   , input [step_width_lp-1:0] down_i

   , output logic [ptr_width_lp-1:0] count_o
   );

   always_ff @(posedge clk_i)
     begin
        if (reset_i)
          count_o <= init_val_p;
        else
          count_o <= count_o - down_i + up_i;
     end

`ifdef FORMAL
    reg f_past_valid;
    initial f_past_valid = 1'b0;
    always @(posedge clk_i) f_past_valid <= 1'b1;

    initial assume (reset_i);

    // Realistic caller contract (mirrors upstream's own overflow/underflow
    // $display warnings): the environment never pushes past the configured
    // bound in either direction.
    always @(posedge clk_i) begin
        assume (!(up_i && (count_o == max_val_p)));
        assume (!(down_i && (count_o == 0)));
    end

    always @(posedge clk_i) if (f_past_valid) begin
        assert (count_o <= max_val_p);
    end

    // %INVARIANTS%
`endif
endmodule
