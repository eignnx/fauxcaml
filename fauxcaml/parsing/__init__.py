from fauxcaml.semantics import syntax
from . import lexer
from . import parser


def parse(src_text: str) -> syntax.TopLevelStmts:
    return parser.parser.parse(lexer.lexer.lex(src_text))


def parse_expr(src_text: str) -> syntax.AstNode:
    stmt_txt = src_text + ";;"
    return parse(stmt_txt).stmts[0]

