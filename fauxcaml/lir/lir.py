from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional, List, Tuple, ClassVar, Dict

from fauxcaml.lir import gen_ctx


class ToNasm(ABC):

    @abstractmethod
    def to_nasm(self, ctx: gen_ctx.NasmGenCtx) -> str:
        pass

    @staticmethod
    def annotate(tag):
        """
        A decorator to put on top of `to_nasm` definitions. Will wrap the output
        nasm code with opening and closing tag comments.
        """
        def decorator(f):
            def new_f(*args, **kwargs):
                return "\n".join([
                    f"; <{tag}>",
                    f(*args, **kwargs),
                    f"; </{tag}>",
                ])
            return new_f
        return decorator


class Value(ToNasm, ABC):
    SIZE = None

    def size(self) -> int:
        """Returns the size (in bytes) of the value"""
        return self.SIZE


@dataclass
class Static(Value):
    value: Value

    def to_nasm(self, ctx: gen_ctx.NasmGenCtx) -> str:
        return ""


class Instr(ToNasm, ABC):
    pass


@dataclass
class Label:
    id: int
    custom_name: Optional[str] = None

    def name(self) -> str:
        if self.custom_name is None:
            return f"L{self.id}"
        else:
            return self.custom_name

    def as_instr(self) -> LabelInstr:
        # noinspection PyArgumentList
        return LabelInstr(self.id, self.custom_name)

    def as_value(self) -> LabelRef:
        # noinspection PyArgumentList
        return LabelRef(self.id, self.custom_name)


@dataclass
class LabelInstr(Label, Instr):

    def to_nasm(self, ctx: gen_ctx.NasmGenCtx) -> str:
        return self.name() + ":"


@dataclass
class LabelRef(Label, Value):
    SIZE: ClassVar[int] = 8

    def to_nasm(self, ctx: gen_ctx.NasmGenCtx) -> str:
        return self.name()


class Temp(Value, ABC):
    pass


@dataclass(frozen=True)
class Temp64(Temp):
    """A 64-bit stack-allocated temporary."""
    SIZE: ClassVar[int] = 8

    id: int

    def to_nasm(self, ctx: gen_ctx.NasmGenCtx) -> str:
        bp_offset = ctx.offset_of(self)
        return f"QWORD [rbp{bp_offset:+}]"


@dataclass(frozen=True)
class Temp0(Temp):
    """A virtual temporary. Zero sized."""
    SIZE: ClassVar[int] = 0

    def to_nasm(self, ctx: gen_ctx.NasmGenCtx) -> str:
        raise ValueError("Don't call this function on Temp0 instance!")


class Literal(Value, ABC):
    pass


@dataclass
class I64(Literal):
    SIZE: ClassVar[int] = 8
    val: int

    def to_nasm(self, ctx: gen_ctx.NasmGenCtx) -> str:
        return f"QWORD {self.val}"


@dataclass
class GetElementPtr(Instr):
    """
    Equivalent to `*(self.tuple_ptr + self.offset)` in C. Assumes result is a
    64-bit value.
    """
    ptr: Temp64
    offset: int
    res: Optional[Temp64] = None

    @ToNasm.annotate("GetElementPtr")
    def to_nasm(self, ctx: gen_ctx.NasmGenCtx) -> str:
        return "\n".join([
            f"mov rax, {self.ptr.to_nasm(ctx)}",
            f"mov rax, [rax{self.offset:+}]",
        ] + ([
            f"mov {self.res.to_nasm(ctx)}, rax"
        ] if self.res is not None else []))


@dataclass
class EnvLookup(GetElementPtr):

    def __init__(self, ptr: Temp64, offset: int, res: Optional[Temp64] = None):
        # Skip the fn ptr (label). Assumes all env elements are 8 bytes.
        offset = 8 * offset + 8
        super().__init__(ptr, offset, res)


@dataclass
class CallClosure(Instr):
    fn: Temp64
    arg: Value
    ret: Optional[Temp64] = None  # If `None`, no return value (Unit)

    @ToNasm.annotate("CallClosure")
    def to_nasm(self, ctx: gen_ctx.NasmGenCtx) -> str:
        asm = [
            f"mov rax, {self.fn.to_nasm(ctx)}",
            f"push rax",
            f"push {self.arg.to_nasm(ctx)}",
            f"call [rax]",
        ] + ([
            f"mov {self.ret.to_nasm(ctx)}, rax"
        ] if self.ret is not None else [])

        return "\n".join(asm)


@dataclass
class CreateClosure(Instr):
    fn_lbl: LabelRef
    captures: List[Value]
    ret: Optional[Temp64] = None

    @ToNasm.annotate("CreateClosure")
    def to_nasm(self, ctx: gen_ctx.NasmGenCtx) -> str:

        # The size of a closure is the sum of the sizes of the captured
        # variables + the size of the 8-byte label (function pointer).
        size = sum(val.size() for val in self.captures) + self.fn_lbl.as_value().size()

        asm = [
            # Allocate a `size`-sized block of memory on the heap.
            f"mov rdi, {size}",
            f"call malloc",

            # Store the label (fn ptr) in the first position
            f"mov r8, rax",
            f"mov QWORD [r8], {self.fn_lbl.as_value().to_nasm(ctx)}",
        ]

        # Setup an offset into the closure struct. Will be incremented AFTER
        # the value is put into the struct.
        offset = self.fn_lbl.as_value().size()  # Skip stored fn label.

        if self.captures:
            asm.append("; <ConstructEnvironment>")

        for val in self.captures:

            # Get each captured value, put in `rax`
            asm.append(
                f"mov rax, {val.to_nasm(ctx)}"
            )

            # Store the captured value in the closure struct.
            asm.append(
                f"mov QWORD [r8+{offset}], rax"
            )

            # Increment the offset by the size of the thing that was stored.
            offset += val.size()

        if self.captures:
            asm.append("; <ConstructEnvironment>")

        # Move the ptr to the closure back into `rax`.
        asm.append(
            f"mov rax, r8"
        )

        if self.ret is not None:
            # Store the closure ptr in the result temporary.
            asm.append(
                f"mov {self.ret.to_nasm(ctx)}, rax"
            )

        return "\n".join(asm)


def param_factory(id, size: int = 8):
    def factory():
        if size == 8:
            return Temp64(id)
        elif size == 0:
            return Temp0()
        else:
            raise ValueError
    return factory


PARAM_ID = -1
ENV_ID = -2


@dataclass
class FnDef(ToNasm):
    label: Label
    param: Temp = field(default_factory=param_factory(PARAM_ID))
    env: Temp64 = field(default_factory=param_factory(ENV_ID))
    body: List[Instr] = field(default_factory=list)

    locals: Dict[Temp, int] = field(default_factory=dict)
    current_offset: int = 0  # Base ptr and return addr stored first
    next_temp_id: int = 0

    def __post_init__(self):
        # The param is always located 16 bytes above [rbp], and the env ptr
        # is 24 bytes above [rbp].
        self.locals[self.param] = +16
        self.locals[self.env] = +24

    def local_alloca_size(self) -> int:
        return sum(
            local.size() for local in self.locals.keys()
            if local not in [self.param, self.env]
        )

    @ToNasm.annotate("FnDef")
    def to_nasm(self, ctx: gen_ctx.NasmGenCtx) -> str:
        asm = [
            # Emit the label at the top of the function.
            self.label.as_instr().to_nasm(ctx),

            f"enter {self.local_alloca_size()}, 0"
        ] + [instr.to_nasm(ctx) for instr in self.body] + [
            # Deallocate all the locals.
            f"leave",

            # After returning, deallocate the argument passed in.
            f"ret {self.param.size()}"
        ]

        return "\n".join(asm)

    def new_temp64(self) -> Temp64:
        t = Temp64(self.next_temp_id)
        self.next_temp_id += 1

        # Store and update the offset into the stack
        self.current_offset -= t.size()  # Subtract because the stack grows down!
        self.locals[t] = self.current_offset
        return t


@dataclass
class Comment(Instr):
    text: str

    def to_nasm(self, ctx: gen_ctx.NasmGenCtx) -> str:
        return f";;; {self.text}"
