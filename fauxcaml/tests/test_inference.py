import pytest

from fauxcaml import parsing
from fauxcaml.semantics import check
from fauxcaml.semantics.syntax import Const, Ident, Lambda, Call, Let, If
from fauxcaml.semantics.typ import Int, Bool, Fn, Tuple, List
from fauxcaml.semantics.unifier_set import UnificationError


def test_const():
    """
    3 : int
    """
    checker = check.Checker()
    three = Const(3, Int)
    assert three.infer_type(checker) == Int

    t = Const(True, Bool)
    assert t.infer_type(checker) == Bool


def test_ident():
    """
    x : int
    """
    checker = check.Checker()
    x = Ident("x")
    checker.type_env[x] = Int
    assert x.infer_type(checker) == Int


def test_lambda():
    """
    fun(x) x : t -> t
    """
    checker = check.Checker()

    id = Lambda(Ident("x"), Ident("x"))
    id_type = id.infer_type(checker)

    T = checker.fresh_var()
    equiv_type = Fn(T, T)
    checker.unify(id_type, equiv_type)
    assert True


def test_lambda_zero():
    fn: Lambda = parsing.parse_expr("fun x -> zero x")
    checker = check.Checker()
    fn_type = fn.infer_type(checker)
    assert checker.concretize(fn_type) == Fn(Int, Bool)
    assert fn.body.type == Bool


def test_two_arg_fn_call():
    call = parsing.parse_expr("pair 3 true")
    checker = check.Checker()
    assert checker.concretize(call.infer_type(checker)) == Tuple(Int, Bool)


def test_instantiation_call():
    """
    define id = fun(x) x;
    id(3) : int
    """
    checker = check.Checker()

    id = Lambda(Ident("x"), Ident("x"))
    checker.type_env[Ident("id")] = id.infer_type(checker)

    call = Call(Ident("id"), Const(3, Int))
    assert checker.concretize(call.infer_type(checker)) == Int


def test_simple_let():
    let: Let = parsing.parse_expr("""
        let x = 3 in
        x
    """)

    checker = check.Checker()
    assert checker.concretize(let.infer_type(checker)) == Int
    assert let.right.type == Int


def test_bad_application():
    fn = parsing.parse_expr("""
        fun f -> pair (f 3) (f true)
    """)

    checker = check.Checker()
    with pytest.raises(UnificationError):
        fn.infer_type(checker)


def test_complex_let():
    let = parsing.parse_expr("""
        let f = fun a -> a in
        (f 3, f true)
    """)

    checker = check.Checker()
    inferred = let.infer_type(checker)
    assert checker.concretize(inferred) == Tuple(Int, Bool)


def test_length_fn():
    """
    let length = fun(l)
        if null(l)
            then 0
            else succ(length(tail(l)))
    in length([true, false])
    """
    checker = check.Checker()

    length = Ident("length")
    l = Ident("l")
    tail = Ident("tail")
    succ = Ident("succ")
    null = Ident("null")

    tail_call = Call(tail, l)
    rec_call = Call(length, tail_call)
    succ_call = Call(succ, rec_call)

    if_stmt = If(
        Call(null, l),
        Const(0, Int),
        succ_call
    )

    fn = Lambda(l, if_stmt)

    body = Call(length, Const([True, False], List(Bool)))
    let = Let(length, fn, body)

    inferred = let.infer_type(checker)
    assert checker.concretize(inferred) == Int


def test_parser_let():
    checker = check.Checker()
    let = parsing.parse_expr("""
        let f = fun x -> x in
        pair (f 3) (f true)
    """)
    inferred = let.infer_type(checker)
    assert checker.concretize(inferred) == Tuple(Int, Bool)


def test_statements():
    checker = check.Checker()
    stmts = parsing.parse("""
        let f x = x + 12;;
        let y = f 12;;
    """)
    stmts.infer_type(checker)
    [let_f, let_y] = stmts.stmts
    y = let_y.left

    assert y.type == Int

