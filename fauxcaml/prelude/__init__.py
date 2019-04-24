from fauxcaml.lir import gen_ctx, lir
from fauxcaml.lir import intrinsics


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

    new_curried_bin_op(ctx, "+", "_$plus", intrinsics.Add)
    new_curried_bin_op(ctx, "-", "_$minus", intrinsics.Sub)
    new_curried_bin_op(ctx, "*", "_$times", intrinsics.Mul)
    new_curried_bin_op(ctx, "div", "_$divide", intrinsics.Div)
    new_curried_bin_op(ctx, "mod", "_$modulo", intrinsics.Mod)
    new_curried_bin_op(ctx, "=", "_$int_is_equal", intrinsics.EqI64)


def new_curried_bin_op(ctx: gen_ctx.NasmGenCtx, name: str, label_name: str, operation):
    with ctx.new_prelude_fn_def(name, label_name) as (lbl, x):

        with ctx.new_prelude_fn_def(name + "$arg2", label_name + "$arg2") as (param_2_lbl, y):
            x_local = ctx.new_temp64()
            ret = ctx.new_temp64()
            ctx.add_instrs([
                lir.EnvLookup(0, x_local),
                operation(x_local, y, ret),
                lir.Return(ret),
            ])

        closure_ret = ctx.new_temp64()
        ctx.add_instrs([
            lir.CreateClosure(param_2_lbl, [x], closure_ret),
            lir.Return(closure_ret),
        ])

