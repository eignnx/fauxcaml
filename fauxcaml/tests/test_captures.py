from fauxcaml import parsing
from fauxcaml.semantics import check
from fauxcaml.semantics import syntax


def test_single_ident():
    x = parsing.parse_expr("""
        x
    """)

    assert x.captures() == {x}


def test_const():
    expr = parsing.parse_expr("""
        1
    """)

    assert expr.captures() == set()


def test_tuple_literal():
    tup = parsing.parse_expr("""
        (x, y, z)
    """)

    assert isinstance(tup, syntax.TupleLit)
    x, y, z = tup.vals
    assert tup.captures() == {x, y, z}


def test_if():
    if_ = parsing.parse_expr("""
        if x
        then y
        else z
    """)

    assert isinstance(if_, syntax.If)
    x, y, z = if_.pred, if_.yes, if_.no
    assert if_.captures() == {x, y, z}


def test_lambda():
    lamb = parsing.parse_expr("""
        fun x -> y + x
    """)

    y = syntax.Ident("y")
    plus = syntax.Ident("+")
    assert lamb.captures() == {y, plus}


def test_let():
    let = parsing.parse_expr("""
        let x = y in
        x + y + z
    """)

    y = syntax.Ident("y")
    z = syntax.Ident("z")
    plus = syntax.Ident("+")

    assert let.captures() == {y, z, plus}


def test_let_stmt_variable():
    let = parsing.parse("""
        let x = f 1;;
    """)

    f = syntax.Ident("f")
    assert let.captures() == {f}


def test_let_stmt_function():
    let = parsing.parse("""
        let f x = g (y + x);;
    """)

    g = syntax.Ident("g")
    y = syntax.Ident("y")
    plus = syntax.Ident("+")
    assert let.captures() == {g, y, plus}


def test_recursive_fn():
    stmts = parsing.parse("""
        let rec fact n =
            if n = 0
            then 1
            else n * fact (n - 1)
        ;;
    """)

    n = syntax.Ident("n")
    fact = syntax.Ident("fact")
    equals = syntax.Ident("=")
    times = syntax.Ident("*")
    minus = syntax.Ident("-")

    assert stmts.captures() == {equals, times, minus}

    assert isinstance(stmts, syntax.TopLevelStmts)
    [let_stmt] = stmts.stmts
    assert isinstance(let_stmt, syntax.LetStmt)
    lamb = let_stmt.right
    assert isinstance(lamb, syntax.Lambda)
    if_ = lamb.body
    assert isinstance(if_, syntax.If)

    assert if_.captures() == {equals, times, minus, n, fact}

    # Decision: a `LetStmt` does NOT capture the name it defines (`fact` in this case), even if it is a recursive
    # definition. (Common sense, I know, but the distinction mattered when writing `LetStmt.to_lir`.)
    assert let_stmt.captures() == {equals, times, minus}


def test_multi_arg_fn():
    stmts = parsing.parse("""
        let f =
            fun x ->
                fun y ->
                    fun z ->
                        let w = 12 in
                        w + x + y + z
        ;;
    """)

    checker = check.Checker()
    stmts.infer_type(checker)

    w = syntax.Ident("w")
    x = syntax.Ident("x")
    y = syntax.Ident("y")
    z = syntax.Ident("z")
    plus = syntax.Ident("+")

    assert stmts.captures() == {plus}

    assert isinstance(stmts, syntax.TopLevelStmts)
    [let_stmt] = stmts.stmts
    assert isinstance(let_stmt, syntax.LetStmt)
    lamb_x = let_stmt.right
    assert isinstance(lamb_x, syntax.Lambda)
    lamb_y = lamb_x.body
    assert isinstance(lamb_y, syntax.Lambda)
    lamb_z = lamb_y.body
    assert isinstance(lamb_z, syntax.Lambda)
    let = lamb_z.body
    assert isinstance(let, syntax.Let)
    body = let.body

    assert body.captures()   == {w, x, y, z, plus}
    assert let.captures()    == {x, y, z, plus}
    assert lamb_z.captures() == {x, y, plus}
    assert lamb_y.captures() == {x, plus}
    assert lamb_x.captures() == {plus}

