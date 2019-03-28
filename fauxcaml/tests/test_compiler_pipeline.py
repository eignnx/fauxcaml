import build
import parsing
from lir import gen_ctx
from semantics import check


def compile_src(src_txt: str) -> gen_ctx.NasmGenCtx:
    checker = check.Checker()
    ctx = gen_ctx.NasmGenCtx()

    ast = parsing.parse(src_txt)
    ast.infer_type(checker)
    _ = ast.to_lir(ctx)
    return ctx


def assert_program_exits_with(ret_code: int, src_txt: str):
    ctx = compile_src(src_txt)
    build.assert_main_returns(ctx, ret_code)


@build.name_asm_file(__file__)
def test_immediate_exit():
    assert_program_exits_with(5, """
        exit 5;;
    """)


@build.name_asm_file(__file__)
def test_immediate_exit_with_arithmetic():
    expected = 2 * (9 // 2 - 7 % 3)
    assert_program_exits_with(expected, """
        exit (2 * (9 div 2 - 7 mod 3));;
    """)


@build.name_asm_file(__file__)
def test_global_variable_lookup():
    assert_program_exits_with(123, """
        let x = 123;;
        exit x;;
    """)


@build.name_asm_file(__file__)
def test_chained_global_variable_lookup():
    assert_program_exits_with(
        7 + (7 * 4) + 45,
        """
        let x = 7;;
        let y = x * 4;;
        let z = x + y + 45;;
        exit z;;
        """
    )


@build.name_asm_file(__file__)
def test_global_function_definition():
    assert_program_exits_with(11, """
        let f x = x + 1;;
        let y = f 10;;
        exit y;;
    """)
    # assert_program_exits_with(11, """
    #     let f x = x + 1;;
    #     exit (f 10);;
    # """)
