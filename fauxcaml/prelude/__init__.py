from fauxcaml.lir import gen_ctx, lir


def add_to_ctx(ctx: gen_ctx.NasmGenCtx):

    with ctx.new_prelude_fn_def("exit", "_$exit") as (lbl, param):
        ctx.add_instr(lir.Nasm("Exit", [
            f"mov rax, 60 ; code for `exit`",
            f"mov rdi, {param.to_nasm_val(ctx)}",
            f"syscall",
        ]))

    # Define `printf`-style format string for printing integers.
    fmt_str_lbl = ctx.new_label("_$print_int_fmt_str")
    fmt_str = lir.StaticByteArray(fmt_str_lbl, ["%d", 0xA, 0x0])
    ctx.statics.append(fmt_str)

    with ctx.new_prelude_fn_def("print_int", "_$print_int") as (lbl, param):
        ctx.add_instr(lir.Nasm("PrintInt", [
            f"mov rdi, {fmt_str_lbl.as_value().to_nasm_val(ctx)}",
            f"mov rsi, {param.to_nasm_val(ctx)}",
            f"call printf",
        ]))
