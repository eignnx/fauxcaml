import rply

from fauxcaml import utils
from fauxcaml.parsing import lexer
from fauxcaml.semantics import typ, syntax

pg = rply.ParserGenerator(
    lexer.all_tokens,
    precedence=[
        ("left", ["SEMI_SEMI"]),
        ("left", ["FUN", "ROCKET"]),
        ("left", ["IF", "THEN", "ELSE"]),
        ("left", ["INT_LIT", "BOOL_LIT", "IDENT"]),
        ("left", ["LET", "REC", "EQ", "IN"]),
        ("left", ["infix_operator"]),
        ("left", ["PLUS", "MINUS"]),
        ("left", ["STAR", "DIV", "MOD"]),
        ("left", ["LPAREN", "RPAREN"]),
        ("left", ["application"]),
    ],
    cache_id="hindley-milner"
)


@pg.production("stmts : stmt stmts")
def stmts(s):
    stmt, stmts = s
    return syntax.TopLevelStmts([stmt]) + stmts


@pg.production("stmts : stmt")
def stmts_singular(s):
    return syntax.TopLevelStmts([s[0]])


@pg.production("stmt : let_stmt")
def stmt(s):
    return s[0]


@pg.production("stmt : expr SEMI_SEMI")
def expr_stmt(s):
    return s[0]


@pg.production("let_stmt : LET decl SEMI_SEMI")
def let_stmt(s):
    _LET, decl, _SEMI_SEMI = s
    return syntax.LetStmt(decl["lhs"], decl["rhs"])


@pg.production("let_stmt : LET REC decl SEMI_SEMI")
def let_stmt(s):
    _LET, _REC, decl, _SEMI_SEMI = s
    return syntax.LetStmt(decl["lhs"], decl["rhs"], recursive=True)


@pg.production("expr : IF expr THEN expr ELSE expr")
def if_expr(s):
    _IF, pred, _THEN, yes, _ELSE, no = s
    return syntax.If(pred, yes, no)


@pg.production("expr : LET REC decl IN expr")
def let_expr(s):
    _LET, _REC, decl, _IN, body = s
    return syntax.Let(decl["lhs"], decl["rhs"], body, recursive=True)


# TODO: Impl type checking for non-rec let exprs.
@pg.production("expr : LET decl IN expr")
def let_expr(s):
    _LET, decl, _IN, expr = s
    return syntax.Let(decl["lhs"], decl["rhs"], expr)


@pg.production("decl : IDENT EQ expr")
def val_decl(s):
    return {
        "lhs": syntax.Ident(s[0].value),
        "rhs": s[2],
    }


@pg.production("decl : IDENT params EQ expr")
def fun_decl(s):
    ident, params, _EQ, body = s
    fn = utils.foldr(syntax.Lambda, params + [body])
    return {
        "lhs": syntax.Ident(ident.value),
        "rhs": fn,
    }


@pg.production("params : IDENT")
def params_single(s):
    return [syntax.Ident(s[0].value)]


@pg.production("params : params IDENT")
def params_multi(s):
    params, ident = s
    return params + [syntax.Ident(ident.value)]


@pg.production("expr : FUN IDENT ROCKET expr")
def fn_expr(s):
    param = syntax.Ident(s[1].value)
    return syntax.Lambda(param, s[3])


@pg.production("expr : expr expr", precedence="application")
def fn_call(s):
    fn, arg = s
    return syntax.Call(fn, arg)


@pg.production("expr : INT_LIT")
def int_lit_expr(s):
    [int_lit] = s
    value = int(int_lit.value)
    return syntax.Const(value, typ.Int)


@pg.production("expr : BOOL_LIT")
def bool_lit_expr(s):
    [bool_lit] = s
    value = {
        "true": True,
        "false": False
    }[bool_lit.value]
    return syntax.Const(value, typ.Bool)


@pg.production("expr : LPAREN tuple_comps RPAREN")
def tuple_expr(s):
    _LPAREN, tuple_comps, _RPAREN = s
    return syntax.TupleLit(*tuple_comps)


@pg.production("tuple_comps : expr COMMA tuple_comps")
def tuple_components_multi(s):
    expr, _COMMA, tuple_comps = s
    return (expr, *tuple_comps)


@pg.production("tuple_comps : expr COMMA expr")
def tuple_components_two(s):
    expr1, _COMMA, expr2 = s
    return (expr1, expr2)


@pg.production("expr : IDENT")
def ident_expr(s):
    [ident] = s
    return syntax.Ident(ident.value)


@pg.production("expr : LPAREN expr RPAREN")
def paren_expr(s):
    _LPAREN, expr, _RPAREN = s
    return expr


@pg.production("expr : expr PLUS expr")
@pg.production("expr : expr MINUS expr")
@pg.production("expr : expr STAR expr")
@pg.production("expr : expr DIV expr")
@pg.production("expr : expr MOD expr")
@pg.production("expr : expr EQ expr", precedence="infix_operator")
def bin_op_expr(s):
    expr1, op, expr2 = s
    ident = syntax.Ident(op.value)
    return syntax.Call(syntax.Call(ident, expr1), expr2)


parser = pg.build()

if __name__ == '__main__':
    def parse(txt):
        return parser.parse(lexer.lexer.lex(txt))

    from fauxcaml.semantics import check
    checker = check.Checker()
    code = """
    let f = fun a -> a in
    (f true, f 13);;
    """
    ast = parse(code)
    print(ast)
    ast.infer_type(checker)
    print(ast.type)
