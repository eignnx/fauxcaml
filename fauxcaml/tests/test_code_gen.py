from fauxcaml.hir import gen_ctx
from fauxcaml.hir import hir
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
        hir.Store(hir.Ident("x", typ.Int), hir.Const(12, typ.Int)),
        hir.Store(hir.Temp(0, typ.Int), hir.Ident("x", typ.Int))
    ]


def test_if():
    ctx = code_gen("""
        if true then 12 else 56
    """)

    assert ctx.current_fn.body == [
        hir.IfFalse(hir.Const(True, typ.Bool), hir.Label(1)),
        hir.Store(hir.Temp(0, typ.Int), hir.Const(12, typ.Int)),
        hir.Goto(hir.Label(2)),
        hir.Label(1),  # Else
        hir.Store(hir.Temp(0, typ.Int), hir.Const(56, typ.Int)),
        hir.Label(2)  # End
    ]


def test_call():
    ctx = code_gen("succ 12")

    succ = hir.Ident(
        "succ",
        typ.Fn(typ.Int, typ.Int)
    )

    assert ctx.current_fn.body == [
        hir.Call(hir.Temp(0, typ.Int), succ, hir.Const(12, typ.Int))
    ]
