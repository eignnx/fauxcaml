import pytest

from fauxcaml import build


@build.name_asm_file(__file__)
def test_immediate_exit():
    assert build.exit_code_for("""
        exit 5;;
    """) == 5


@build.name_asm_file(__file__)
def test_immediate_exit_with_arithmetic():
    assert build.exit_code_for("""
        exit (2 * (9 div 2 - 7 mod 3));;
    """) == 2 * (9 // 2 - 7 % 3)


@build.name_asm_file(__file__)
def test_global_variable_lookup():
    assert build.exit_code_for("""
        let x = 123;;
        exit x;;
    """) == 123


@build.name_asm_file(__file__)
def test_chained_global_variable_lookup():
    assert build.exit_code_for("""
        let x = 7;;
        let y = x * 4;;
        let z = x + y + 45;;
        exit z;;
    """) == 7 + (7 * 4) + 45


@build.name_asm_file(__file__)
def test_global_function_definition():
    assert build.exit_code_for("""
        let f x = x + 1;;
        exit (f 100);;
    """) == 101


@build.name_asm_file(__file__)
def test_two_parameter_function():
    assert build.exit_code_for("""
        let plus x y =
            x + y;;
        exit (plus 100 50);;
    """) == 150


@build.name_asm_file(__file__)
def test_three_parameter_function():
    assert build.exit_code_for("""
        let plus x y z =
            x + y + z;;
        exit (plus 100 50 25);;
    """) == 175


@build.name_asm_file(__file__)
def test_adder_factory():
    assert build.exit_code_for("""
        let adder x y =
            x + y
        ;;
        let plus77 = adder 77;;
        exit (plus77 99);;
    """) == 77 + 99


@build.name_asm_file(__file__)
def test_closure_capture():
    assert build.exit_code_for("""
        let y = 10;;
        let f x =
            x + y
        ;;
        exit (f 20);;
    """) == 30


@build.name_asm_file(__file__)
def test_nested_if_expressions():
    assert build.exit_code_for("""
        let res =
            if 1 = 1
            then if 3 = 4
                 then 5
                 else 6
            else 7
        ;;
        exit res;;
    """) == 6


@build.name_asm_file(__file__)
def test_factorial():
    assert build.exit_code_for("""
        let rec fact n =
            if n = 1
            then 1
            else n * (fact (n - 1))
        ;;
        exit (fact 5);;
    """) == 120


@build.name_asm_file(__file__)
def test_nested_let_expr():
    assert build.exit_code_for("""
        let my_main x =
            let y = x + 1 in
            let z = y + 1 in
            let w = x + y + z in
            w
        ;;
        exit (my_main 0);;
    """) == 3


@pytest.mark.xfail(reason="Stdout capture inside tests not yet impl'd.")
@build.name_asm_file(__file__)
def test_print_int(capsys):
    assert build.stdout_log_for("""
        print_int 123456789;;
        print_int 987654321;;
        exit 0;;
    """, capsys) == "123456789\n987654321\n"


@build.name_asm_file(__file__)
def test_reassigning_exit():
    assert build.exit_code_for("""
        let my_exit = exit;;
        my_exit 12;;
        exit 99;;
    """) == 12


@build.name_asm_file(__file__)
def test_wrapping_exit():
    assert build.exit_code_for("""
        let my_exit x = exit x;;
        my_exit 12;;
        exit 99;;
    """) == 12
