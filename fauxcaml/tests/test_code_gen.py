from fauxcaml.code_gen import gen_ctx
from fauxcaml.code_gen import ir
from fauxcaml import parsing
from fauxcaml.semantics import check
from fauxcaml.semantics import typ


def code_gen(src: str) -> gen_ctx.CodeGenContext:
    ast = parsing.parse(src)
    checker = check.Checker()
    _ = ast.infer_type(checker)
    ctx = gen_ctx.CodeGenContext()
    ast.code_gen(ctx)
    return ctx


def test_let():
    ctx = code_gen("""
        let
            val x = 12
        in
            x
        end
    """)

    assert ctx.current_fn.body == [
        ir.Store(ir.Ident("x", typ.Int), ir.Const(12, typ.Int)),
        ir.Store(ir.Temp(0, typ.Int), ir.Ident("x", typ.Int))
    ]


def test_if():
    ctx = code_gen("""
        if true then 12 else 56
    """)

    assert ctx.current_fn.body == [
        ir.IfFalse(ir.Const(True, typ.Bool), ir.Label(1)),
        ir.Store(ir.Temp(0, typ.Int), ir.Const(12, typ.Int)),
        ir.Goto(ir.Label(2)),
        ir.Label(1),  # Else
        ir.Store(ir.Temp(0, typ.Int), ir.Const(56, typ.Int)),
        ir.Label(2)  # End
    ]


def test_call():
    ctx = code_gen("succ 12")

    succ = ir.Ident(
        "succ",
        typ.Fn(typ.Int, typ.Int)
    )

    assert ctx.current_fn.body == [
        ir.Call(ir.Temp(0, typ.Int), succ, ir.Const(12, typ.Int))
    ]
