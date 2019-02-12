from typing import List

from fauxcaml.code_gen.ir import *


def get_program():
    """
    Example taken from Compilers, Principles, Techniques, & Tools, Second
    Edition, Aho, Lam, Sethi, Ullman, pg. 527.

    for i from 1 to 10 do
        for j from 1 to 10 do
            a[i, j] = 0.0;
    for i from 1 to 10 do
        a[i, j] = 1.0;

    Assumes 8-byte floating point values.
    """
    return [
        Store(Ident("i", int), Const(1, int)),
        Label(1),
        Store(Ident("j", int), Const(1, int)),
        Label(0),
        BinaryOp("*", Temp(1, int), Const(10, int), Ident("i", int)),
        BinaryOp("+", Temp(2, int), Temp(1, int), Ident("j", int)),
        BinaryOp("*", Temp(3, int), Const(8, int), Temp(2, int)),
        BinaryOp("-", Temp(4, int), Temp(3, int), Const(88, int)),
        ArrayStore(Ident("a", List[float]), Temp(4, int), Const(0.0, float)),
        BinaryOp("+", Ident("j", int), Ident("j", int), Const(1, int)),
        BinaryOp(">", Temp(10, bool), Ident("j", int), Const(10, int)),
        IfFalse(Temp(10, bool), Label(0)),
        BinaryOp("+", Ident("i", int), Ident("i", int), Const(1, int)),
        BinaryOp(">", Temp(11, bool), Ident("i", int), Const(10, int)),
        IfFalse(Temp(11, bool), Label(1)),
        Store(Ident("i", int), Const(1, int)),
        Label(2),
        BinaryOp("-", Temp(5, int), Ident("i", int), Const(1, int)),
        BinaryOp("*", Temp(6, int), Const(88, int), Temp(5, int)),
        ArrayStore(Ident("a", List[float]), Temp(6, int), Const(1.0, float)),
        BinaryOp("+", Ident("i", int), Ident("i", int), Const(1, int)),
        BinaryOp(">", Temp(12, bool), Ident("i", int), Const(10, int)),
        IfFalse(Temp(12, bool), Label(2)),
    ]


def test_construction_of_instructions():
    program = [
        Store(Temp(1, int), Const(123, int)),
        ArrayStore(Ident("x", List[bool]), Const(3, int), Temp(2, bool)),
        ArrayLoad(Temp(3, int), Ident("arr", List[int]), Const(4, int)),
        UnaryOp("-", Ident("y", int), Temp(4, int)),
        BinaryOp("+", Ident("y", float), Const(3, float), Temp(5, float)),
    ]


def test_identifying_leaders():
    program = get_program()

