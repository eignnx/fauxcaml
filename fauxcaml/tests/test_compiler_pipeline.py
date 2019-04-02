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
        let add x y =
            x + y;;
        exit (add 100 50);;
    """) == 150


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