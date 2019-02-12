import rply

from fauxcaml.semantics import check
from fauxcaml.semantics import unifier_set
from fauxcaml.semantics import env
from fauxcaml import parsing


def repl():
    checker = check.Checker()

    while True:
        inp = input("==> ")

        try:
            ast = parsing.parse(inp)
        except rply.errors.LexingError as err:
            idx = err.source_pos.idx
            lineno = err.source_pos.lineno
            colno = err.source_pos.colno

            if lineno < 0 and colno < 0:
                pos = f"at index {idx}"
            else:
                pos = f"on line {lineno}, column {colno} "

            print(f"Lexing Error: Unexpected character {pos}!")
            continue
        except rply.errors.ParsingError as err:
            lineno = err.source_pos.lineno
            colno = err.source_pos.colno
            print(f"Parsing Error: Unexpected token on line {lineno}, column {colno}!")
            continue

        try:
            t = ast.infer_type(checker)
            t = checker.unifiers.concretize(t)
            print(f"_ : {t}")
        except env.EnvKeyError as err:
            print(f"Semantic Error: Unrecognized symbol '{err.key}'!")
            continue
        except unifier_set.UnificationError as err:
            print(err.msg)
            continue


if __name__ == '__main__':
    repl()
