from fauxcaml.lir import intrinsics, gen_ctx


def add_to_ctx(ctx: gen_ctx.NasmGenCtx):

    with ctx.new_prelude_fn_def("exit", "_$exit") as (lbl, param):
        ctx.add_instr(
            intrinsics.Exit(param)
        )

    with ctx.new_prelude_fn_def("print_int", "_$print_int") as (lbl, param):
        ctx.add_instr(
            intrinsics.PrintInt(param)
        )
