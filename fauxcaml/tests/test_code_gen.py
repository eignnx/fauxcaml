from fauxcaml.code_gen import gen_ctx
from fauxcaml.code_gen import ir
from fauxcaml import parsing
from fauxcaml.semantics import check
from fauxcaml.semantics import typ


def test_let():
    let = parsing.parse("""
        let
            val x = 12
        in
            x
        end
    """)
    checker = check.Checker()
    _ = let.infer_type(checker)

    ctx = gen_ctx.CodeGenContext()
    let.code_gen(ctx)

    assert ctx.current_fn.body == [
        ir.Store(ir.Ident("x", typ.Int), ir.Const(12, typ.Int)),
        ir.Store(ir.Temp(0, typ.Int), ir.Ident("x", typ.Int))
    ]


