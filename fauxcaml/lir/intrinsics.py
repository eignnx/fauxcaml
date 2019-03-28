from __future__ import annotations

from abc import ABC
from dataclasses import dataclass
from typing import Optional, List

from fauxcaml.lir import lir, gen_ctx


@dataclass
class IntrinsicFnDef(lir.ToTgt, ABC):
    pass


@dataclass
class IntrinsicCall(lir.Instr, ABC):
    pass


@dataclass
class CreateTuple(IntrinsicCall):
    values: List[lir.Value]
    ret: lir.Temp64

    @lir.ToTgt.annotate("CreateTuple", arity="len(values)")
    def to_nasm(self, ctx: gen_ctx.NasmGenCtx) -> List[str]:
        return [
            f"mov rdi, {len(self.values) * 8}",
            f"call malloc",
            f"mov {self.ret.to_nasm_val(ctx)}, rax",
        ] + [
            line  # Python's ugly flatmap...
            for i, value in enumerate(self.values)
            for line in lir.SetElementPtr(
                ptr=self.ret,
                index=i,
                stride=8,
                value=value
            ).to_nasm(ctx)
        ]


@dataclass
class AddSub(IntrinsicCall):
    op: str
    arg1: lir.Value
    arg2: lir.Value

    # Optionally store result in temp in addition to `rax`.
    res: Optional[lir.Temp] = None

    def __post_init__(self):
        assert self.op in {"+", "-"}

    @lir.ToTgt.annotate("AddSub", operation="op")
    def to_nasm(self, ctx: gen_ctx.NasmGenCtx) -> List[str]:
        op = {
            "+": "add",
            "-": "sub",
        }[self.op]
        return [
            f"mov rax, {self.arg1.to_nasm_val(ctx)}",
            f"{op} rax, {self.arg2.to_nasm_val(ctx)}",
        ] + ([
            f"mov {self.res.to_nasm_val(ctx)}, rax"
        ] if self.res is not None else [])


# noinspection PyPep8Naming
def Add(arg1: lir.Value, arg2: lir.Value, res: Optional[lir.Temp] = None) -> AddSub:
    return AddSub("+", arg1, arg2, res)


# noinspection PyPep8Naming
def Sub(arg1: lir.Value, arg2: lir.Value, res: Optional[lir.Temp] = None) -> AddSub:
    return AddSub("-", arg1, arg2, res)


@dataclass
class MulDivMod(IntrinsicCall):
    op: str
    arg1: lir.Value
    arg2: lir.Value
    res: lir.Temp64

    def __post_init__(self):
        assert self.op in {"*", "div", "mod"}

    @lir.ToTgt.annotate("MulDivMod", operation="op")
    def to_nasm(self, ctx: gen_ctx.NasmGenCtx) -> List[str]:

        instr = {
            "*": "mul",
            "div": "div",
            "mod": "div",
        }[self.op]

        return ([
            # Zero out top bits of dividend.
            f"xor rdx, rdx"
        ] if instr == "div" else []) + [
            f"mov rax, {self.arg1.to_nasm_val(ctx)}",
            f"mov r8, {self.arg2.to_nasm_val(ctx)}",
            f"{instr} r8",
        ] + ([
            # Move the remainder into the result register.
            f"mov rax, rdx"
        ] if self.op == "mod" else []) + [
            f"mov {self.res.to_nasm_val(ctx)}, rax"
        ]


# noinspection PyPep8Naming
def Mul(arg1: lir.Value, arg2: lir.Value, res: lir.Temp64) -> MulDivMod:
    return MulDivMod("*", arg1, arg2, res)


# noinspection PyPep8Naming
def Div(arg1: lir.Value, arg2: lir.Value, res: lir.Temp64) -> MulDivMod:
    return MulDivMod("div", arg1, arg2, res)


# noinspection PyPep8Naming
def Mod(arg1: lir.Value, arg2: lir.Value, res: lir.Temp64) -> MulDivMod:
    return MulDivMod("mod", arg1, arg2, res)


@dataclass
class EqI64(IntrinsicCall):
    arg1: lir.Value
    arg2: lir.Value
    ret: lir.Temp64

    @lir.ToTgt.annotate("EqI64")
    def to_nasm(self, ctx: gen_ctx.NasmGenCtx) -> List[str]:
        return [
            f"mov rax, {self.arg1.to_nasm_val(ctx)}",
            f"cmp rax, {self.arg2.to_nasm_val(ctx)}",
            f"sete al",
            f"mov {self.ret.to_nasm_val(ctx)}, rax",
        ]


@dataclass
class Exit(IntrinsicCall):
    arg: lir.Value

    @lir.ToTgt.annotate("Exit")
    def to_nasm(self, ctx: gen_ctx.NasmGenCtx) -> List[str]:
        return [
            f"mov rax, 60 ; code for `exit`",
            f"mov rdi, {self.arg.to_nasm_val(ctx)}",
            f"syscall",
        ]
