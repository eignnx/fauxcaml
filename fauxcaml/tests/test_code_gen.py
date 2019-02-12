from fauxcaml.code_gen import gen_ctx
from fauxcaml import parsing
from fauxcaml.semantics import check

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


