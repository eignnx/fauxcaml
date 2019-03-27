from abc import ABC
from dataclasses import dataclass
from typing import List

from fauxcaml.semantics import typ, env


class Value(ABC):
    pass


class Addr(Value):
    pass


@dataclass
class Ident(Addr):
    id: int
    type: typ.Type


@dataclass
class Capture(Addr):
    path: List[int]
    type: typ.Type


@dataclass
class Temp(Addr):
    id: int
    type: typ.Type


@dataclass
class Const(Value):
    value: object
    type: typ.Type

    def __str__(self):
        return f"{self.value}: {self.type}"


class Instr(ABC):
    __slots__ = ()


@dataclass
class Store(Instr):
    lhs: Addr
    rhs: Value


@dataclass
class ArrayStore(Instr):
    arr: Value
    index: Value
    rhs: Value


@dataclass
class ArrayLoad(Instr):
    lhs: Addr
    arr: Value
    index: Value


@dataclass
class Label(Instr, Value):
    id: int

    def __str__(self):
        return f"L{self.id}:"


@dataclass
class UnaryOp(Instr):
    op: str
    lhs: Addr
    arg: Value


@dataclass
class BinaryOp(Instr):
    op: str
    lhs: Addr
    arg1: Value
    arg2: Value


@dataclass
class IfFalse(Instr):
    cond: Value
    label: Label


@dataclass
class Call(Instr):
    res: Addr
    fn: Addr  # Label (maybe in deeper hir)
    arg: Value


@dataclass
class Goto(Instr):
    label: Label


@dataclass
class FnDecl:
    label: Label
    param: Ident
    body: List[Instr]
    env: env.Env[Ident, object]  # TODO: Decide what `object` should be replaced with here
