from fauxcaml.lir import intrinsics, gen_ctx, lir


def add_to_ctx(ctx: gen_ctx.NasmGenCtx):

    with ctx.new_prelude_fn_def("exit", "_$exit") as (lbl, param):
        ctx.add_instr(
            intrinsics.Exit(param)
        )

    # Define `printf`-style format string for printing integers.
    fmt_str_lbl = ctx.new_label("_$print_int_fmt_str")
    fmt_str = lir.StaticByteArray(fmt_str_lbl, ["%d", 0xA, 0x0])
    ctx.statics.append(fmt_str)

    with ctx.new_prelude_fn_def("print_int", "_$print_int") as (lbl, param):
        ctx.add_instr(
            intrinsics.PrintInt(param)
        )
