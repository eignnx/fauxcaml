from __future__ import annotations

from fauxcaml.semantics import check
from fauxcaml.semantics import env
from fauxcaml.semantics import syntax
from fauxcaml.semantics import typ


def std_env(checker: check.Checker) -> env.Env[syntax.Ident, typ.Type]:
    T = checker.fresh_var()
    U = checker.fresh_var()
    V = checker.fresh_var()
    W = checker.fresh_var()

    return env.Env(locals={
        syntax.Ident("null"): typ.Fn(typ.List(T), typ.Bool),
        syntax.Ident("tail"): typ.Fn(typ.List(U), typ.List(U)),
        syntax.Ident("zero"): typ.Fn(typ.Int, typ.Bool),
        syntax.Ident("succ"): typ.Fn(typ.Int, typ.Int),
        syntax.Ident("pred"): typ.Fn(typ.Int, typ.Int),
        syntax.Ident("times"): typ.Fn(typ.Int, typ.Fn(typ.Int, typ.Int)),
        syntax.Ident("pair"): typ.Fn(V, typ.Fn(W, typ.Tuple(V, W))),

        syntax.Ident("+"): typ.Fn(typ.Tuple(typ.Int, typ.Int), typ.Int),
        syntax.Ident("-"): typ.Fn(typ.Tuple(typ.Int, typ.Int), typ.Int),
        syntax.Ident("*"): typ.Fn(typ.Tuple(typ.Int, typ.Int), typ.Int),
        syntax.Ident("div"): typ.Fn(typ.Tuple(typ.Int, typ.Int), typ.Int),
        syntax.Ident("mod"): typ.Fn(typ.Tuple(typ.Int, typ.Int), typ.Int),
        syntax.Ident("="): typ.Fn(typ.Tuple(typ.Int, typ.Int), typ.Bool),

        syntax.Ident("exit"): typ.Fn(typ.Int, typ.Unit),
    })
