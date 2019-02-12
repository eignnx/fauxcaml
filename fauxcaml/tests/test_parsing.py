from fauxcaml.parsing import parse
from fauxcaml.semantics.syntax import Ident, Const, Lambda, Call, Let, If
from fauxcaml.semantics.typ import Int, Bool


def test_if_stmt():
    parsed_if = parse("if true then succ 3 else pred 5")

    three = Const(3, Int)
    five = Const(5, Int)
    true = Const(True, Bool)
    pred = Ident("pred")
    pred_call = Call(pred, five)
    succ = Ident("succ")
    succ_call = Call(succ, three)
    built_if = If(true, succ_call, pred_call)

    assert parsed_if == built_if


def test_fun_decl_in_let():
    fun_decl = parse("""
        let
          fun f x y z = 1
        in
          f
        end
    """)

    nested_lambda = parse("""
        let
          val f = fn x => fn y => fn z => 1
        in
          f
        end
    """)

    assert fun_decl == nested_lambda




def test_lambda():
    parsed_fn = parse("fn x => zero x")
    built_fn = Lambda(Ident("x"), Call(Ident("zero"), Ident("x")))
    assert parsed_fn == built_fn


def test_curried_fn_call():
    parsed_call = parse("pair 3 true")

    pair = Ident("pair")
    three = Const(3, Int)
    true = Const(True, Bool)
    built_call = Call(Call(pair, three), true)

    assert parsed_call == built_call


def test_complex_let():
    parsed_let = parse("""
        let
          val f = fn a => a
        in
          pair (f 3) (f true)
        end
    """)

    f = Ident("f")
    a = Ident("a")
    three = Const(3, Int)
    true = Const(True, Bool)
    pair = Ident("pair")

    fn = Lambda(a, a)

    f_of_3 = Call(f, three)
    f_of_true = Call(f, true)
    pair_call = Call(Call(pair, f_of_3), f_of_true)

    built_let = Let(f, fn, pair_call)

    assert parsed_let == built_let
