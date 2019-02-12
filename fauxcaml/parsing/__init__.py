from fauxcaml.semantics import syntax
from . import parser
from . import lexer


def parse(src_text: str) -> syntax.AstNode:
    return parser.parser.parse(lexer.lexer.lex(src_text))

