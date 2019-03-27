from fauxcaml import parsing
from fauxcaml.hir import gen_ctx
from fauxcaml.semantics import check


def code_gen(src: str) -> gen_ctx.CodeGenContext:
    ast = parsing.parse(src)
    checker = check.Checker()
    _ = ast.infer_type(checker)
    ctx = gen_ctx.CodeGenContext()
    # ast.code_gen(ctx)
    return ctx


def test_let():
    ctx = code_gen("""
        let x = 12 in
        x;;
    """)


def test_if():
    ctx = code_gen("""
        if true then 12 else 56;;
    """)


def test_call():
    ctx = code_gen("succ 12;;")

