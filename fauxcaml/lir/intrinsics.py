from __future__ import annotations

from abc import ABC
from dataclasses import dataclass
from typing import Optional

from fauxcaml.lir import lir, gen_ctx
from fauxcaml.semantics import typ


@dataclass
class IntrinsicFn(lir.Instr, ABC):
    signature: typ.Type


@dataclass
class IntrinsicCall(lir.Instr, ABC):
    pass


@dataclass
class AddSub(IntrinsicCall):
    op: str
    arg1: lir.Value
    arg2: lir.Value

    # Optionally store result in temp in addition to `rax`.
    res: Optional[lir.Temp] = None

    def __post_init__(self):
        assert self.op in {"add", "sub"}

    def to_nasm(self, ctx: gen_ctx.NasmGenCtx) -> str:
        asm = [
            f"mov rax, {self.arg1.to_nasm(ctx)}",
            f"{self.op} rax, {self.arg2.to_nasm(ctx)}",
        ]

        if self.res is not None:
            asm.append(
                f"mov {self.res.to_nasm(ctx)}, rax"
            )

        return "\n".join(asm)


# noinspection PyPep8Naming
def Add(arg1: lir.Value, arg2: lir.Value, res: Optional[lir.Temp] = None) -> AddSub:
    return AddSub("add", arg1, arg2, res)


# noinspection PyPep8Naming
def Sub(arg1: lir.Value, arg2: lir.Value, res: Optional[lir.Temp] = None) -> AddSub:
    return AddSub("sub", arg1, arg2, res)


@dataclass
class MulDivMod(IntrinsicCall):
    op: str
    arg1: lir.Value
    arg2: lir.Value

    # Optionally store result in temp in addition to `rax`.
    res: Optional[lir.Temp] = None

    @lir.ToNasm.annotate("MulDivMod")
    def to_nasm(self, ctx: gen_ctx.NasmGenCtx) -> str:

        instr = {
            "mul": "mul",
            "div": "div",
            "mod": "div",
        }[self.op]

        asm = ([
            # Zero out top bits of dividend.
            f"xor rdx, rdx"
        ] if instr == "div" else []) + [
            f"mov rax, {self.arg1.to_nasm(ctx)}",
            f"mov r8, {self.arg2.to_nasm(ctx)}",
            f"{instr} r8",
        ] + ([
            # Move the remainder into the result register.
            f"mov rax, rdx"
        ] if self.op == "mod" else []) + ([
            f"mov {self.res.to_nasm(ctx)}, rax"
        ] if self.res is not None else [])

        return "\n".join(asm)


# noinspection PyPep8Naming
def Mul(arg1: lir.Value, arg2: lir.Value, res: Optional[lir.Temp] = None) -> MulDivMod:
    return MulDivMod("mul", arg1, arg2, res)


# noinspection PyPep8Naming
def Div(arg1: lir.Value, arg2: lir.Value, res: Optional[lir.Temp] = None) -> MulDivMod:
    return MulDivMod("div", arg1, arg2, res)


# noinspection PyPep8Naming
def Mod(arg1: lir.Value, arg2: lir.Value, res: Optional[lir.Temp] = None) -> MulDivMod:
    return MulDivMod("mod", arg1, arg2, res)

