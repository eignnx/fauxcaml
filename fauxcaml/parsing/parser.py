import rply

from fauxcaml.semantics import typ, syntax
from fauxcaml import utils
from fauxcaml.parsing import lexer

pg = rply.ParserGenerator(
    lexer.all_tokens,
    precedence=[
        ("left", ["FN", "ROCKET"]),
        ("left", ["IF", "THEN", "ELSE"]),
        ("left", ["INT_LIT", "BOOL_LIT", "IDENT"]),
        ("left", ["VAL", "FUN"]),
        ("left", ["LET", "EQ", "IN", "END"]),
        ("left", ["LPAREN", "RPAREN"]),
        ("left", ["application"]),
    ],
    cache_id="hindley-milner"
)


@pg.production("expr : IF expr THEN expr ELSE expr")
def if_expr(s):
    return syntax.If(s[1], s[3], s[5])


@pg.production("expr : LET decl IN expr END")
def let_expr(s):
    decl = s[1]
    return syntax.Let(decl["lhs"], decl["rhs"], s[3])


@pg.production("decl : VAL IDENT EQ expr")
def val_decl(s):
    return {
        "lhs": syntax.Ident(s[1].value),
        "rhs": s[3],
    }


@pg.production("decl : FUN IDENT params EQ expr")
def fun_decl(s):
    params = s[2]
    body = s[4]
    fn = utils.foldr(syntax.Lambda, params + [body])
    return {
        "lhs": syntax.Ident(s[1].value),
        "rhs": fn,
    }


@pg.production("params : IDENT")
def params_single(s):
    return [syntax.Ident(s[0].value)]


@pg.production("params : params IDENT")
def params_multi(s):
    return s[0] + [syntax.Ident(s[1].value)]


@pg.production("expr : FN IDENT ROCKET expr")
def fn_expr(s):
    param = syntax.Ident(s[1].value)
    return syntax.Lambda(param, s[3])


@pg.production("expr : expr expr", precedence="application")
def fn_call(s):
    return syntax.Call(s[0], s[1])


@pg.production("expr : INT_LIT")
def int_lit_expr(s):
    value = int(s[0].value)
    return syntax.Const(value, typ.Int)


@pg.production("expr : BOOL_LIT")
def bool_lit_expr(s):
    value = {
        "true": True,
        "false": False
    }[s[0].value]
    return syntax.Const(value, typ.Bool)


@pg.production("expr : IDENT")
def ident_expr(s):
    return syntax.Ident(s[0].value)


@pg.production("expr : LPAREN expr RPAREN")
def paren_expr(s):
    return s[1]


parser = pg.build()

if __name__ == '__main__':
    def parse(txt):
        return parser.parse(lexer.lexer.lex(txt))

    from fauxcaml.semantics.src import Checker
    checker = Checker()
    code = "let val f = fn a => a in pair (f true) (f 13) end"
    ast = parse(code)
    print(ast)
    ast.infer_type(checker)
