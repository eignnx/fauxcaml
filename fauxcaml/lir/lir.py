from __future__ import annotations

import functools
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional, List, Tuple, ClassVar, Dict

from fauxcaml.lir import gen_ctx


class ToTgt(ABC):

    @abstractmethod
    def to_nasm(self, ctx: gen_ctx.NasmGenCtx) -> List[str]:
        pass

    @staticmethod
    def annotate(tag, **attrs):
        """
        A decorator to put on top of `to_nasm` definitions. Will wrap the output
        nasm code with opening and closing tag comments.
        """
        def decorator(f):
            @functools.wraps(f)
            def new_f(self, *args, **kwargs):

                # noinspection PyShadowingNames
                props = ", ".join(
                    f"{prop}=\"{eval(expr, globals(), {'self': self})}\""
                    for prop, expr in attrs.items()
                )

                space = " " if props else ""

                return [
                    f"; <{tag}{space}{props}>",
                    *(
                        "    " + line
                        for line in f(self, *args, **kwargs)
                    ),
                    f"; </{tag}>",
                ]
            return new_f
        return decorator


class ToTgtVal(ABC):

    @abstractmethod
    def to_nasm_val(self, ctx: gen_ctx.NasmGenCtx) -> str:
        pass


class Value(ToTgtVal, ABC):
    SIZE = None

    def size(self) -> int:
        """Returns the size (in bytes) of the value"""
        return self.SIZE


@dataclass
class Static(Value):
    value: Value

    def to_nasm_val(self, ctx: gen_ctx.NasmGenCtx) -> str:
        return ""


class Instr(ToTgt, ABC):
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

    def to_nasm(self, ctx: gen_ctx.NasmGenCtx) -> List[str]:
        return [self.name() + ":"]


@dataclass
class LabelRef(Label, Value):
    SIZE: ClassVar[int] = 8

    def to_nasm_val(self, ctx: gen_ctx.NasmGenCtx) -> str:
        return self.name()


class Temp(Value, ABC):
    pass


@dataclass(frozen=True)
class Temp64(Temp):
    """A 64-bit stack-allocated temporary."""
    SIZE: ClassVar[int] = 8

    id: int

    def to_nasm_val(self, ctx: gen_ctx.NasmGenCtx) -> str:
        bp_offset = ctx.offset_of(self)
        return f"QWORD [rbp{bp_offset:+}]"


@dataclass(frozen=True)
class Temp0(Temp):
    """A virtual temporary. Zero sized."""
    SIZE: ClassVar[int] = 0

    def to_nasm_val(self, ctx: gen_ctx.NasmGenCtx) -> str:
        raise ValueError("Don't call this function on Temp0 instance!")


class Literal(Value, ABC):
    pass


@dataclass
class I64(Literal):
    SIZE: ClassVar[int] = 8
    val: int

    def to_nasm_val(self, ctx: gen_ctx.NasmGenCtx) -> str:
        return f"QWORD {self.val}"


@dataclass
class GetElementPtr(Instr):
    """
    Equivalent to:

    ```c
    *(u_int64 *)(
        ((char *) self.tuple_ptr) + self.index * self.stride
    )
    ```

    TODO: Assumes result is a 64-bit value.
    TODO: `self.index` currently can't be set by runtime value. (Maybe ok if no arrays, only lists?)
    """
    ptr: Temp
    index: int
    stride: int
    res: Optional[Temp64] = None

    @ToTgt.annotate("GetElementPtr", stride="self.stride")
    def to_nasm(self, ctx: gen_ctx.NasmGenCtx) -> List[str]:
        if self.ptr.size() == 0:
            raise ValueError("Cannot perform GetElementPtr on zero-sized temporary!")

        offset = self.stride * self.index
        return [
            f"mov rax, {self.ptr.to_nasm_val(ctx)}",
            f"mov rax, [rax{offset:+}]",
        ] + ([
            f"mov {self.res.to_nasm_val(ctx)}, rax"
        ] if self.res is not None else [])


@dataclass
class SetElementPtr(Instr):
    ptr: Temp64
    index: int
    stride: int
    value: Value

    @ToTgt.annotate("SetElementPtr", stride="self.stride")
    def to_nasm(self, ctx: gen_ctx.NasmGenCtx) -> List[str]:
        offset = self.stride * self.index
        return [
            f"mov rax, {self.ptr.to_nasm_val(ctx)}",
            f"mov r8, {self.value.to_nasm_val(ctx)}",
            f"mov [rax{offset:+}], r8",
        ]


@dataclass
class EnvLookup(Instr):
    index: int
    res: Optional[Temp64] = None

    @ToTgt.annotate("EnvLookup", index="self.index")
    def to_nasm(self, ctx: gen_ctx.NasmGenCtx) -> List[str]:
        return GetElementPtr(
            ptr=ctx.current_fn.env,

            # Skip the fn ptr (label).
            index=self.index + 1,

            # Assumes all env elements are 8 bytes.
            stride=8,
            res=self.res
        ).to_nasm(ctx)


@dataclass
class CallClosure(Instr):
    fn: Temp64
    arg: Value
    ret: Optional[Temp64] = None  # If `None`, no return value (Unit)

    @ToTgt.annotate("CallClosure")
    def to_nasm(self, ctx: gen_ctx.NasmGenCtx) -> List[str]:
        return [
            f"mov rax, {self.fn.to_nasm_val(ctx)}",
            f"push rax",
            f"push {self.arg.to_nasm_val(ctx)}",
            f"call [rax]",
        ] + ([
            f"mov {self.ret.to_nasm_val(ctx)}, rax"
        ] if self.ret is not None else [])


@dataclass
class CreateClosure(Instr):
    fn_lbl: LabelRef
    captures: List[Value]
    ret: Optional[Temp64] = None
    recursive: bool = False

    @ToTgt.annotate("CreateClosure", recursive="self.recursive")
    def to_nasm(self, ctx: gen_ctx.NasmGenCtx) -> List[str]:

        # The size of a closure is the sum of the sizes of the captured
        # variables + the size of the 8-byte label (function pointer).
        size = sum(val.size() for val in self.captures) + self.fn_lbl.as_value().size()

        asm = [
            # Allocate a `size`-sized block of memory on the heap.
            f"mov rdi, {size}",
            f"call malloc",

            # Store the label (fn ptr) in the first position
            f"mov r8, rax",
            f"mov QWORD [r8], {self.fn_lbl.as_value().to_nasm_val(ctx)}",
        ]

        # Setup an offset into the closure struct. Will be incremented AFTER
        # the value is put into the struct.
        offset = self.fn_lbl.as_value().size()  # Skip stored fn label.

        if self.captures:
            asm.append("; <ConstructEnvironment>")

            for val in self.captures:
                asm += [
                    # Get each captured value, put in `rax`
                    f"mov rax, {val.to_nasm_val(ctx)}"
                    
                    # Store the captured value in the closure struct.
                    f"mov QWORD [r8{offset:+}], rax"
                ]

                # Increment the offset by the size of the thing that was stored.
                offset += val.size()

            asm.append("; </ConstructEnvironment>")

        # If the function is recursive, the pointer to the closure must be
        # stored in the environment too.
        if self.recursive:
            asm.append(
                f"mov [r8{offset:+}], r8"
            )
            offset += 8

        # Move the ptr to the closure back into `rax`.
        asm.append(
            f"mov rax, r8"
        )

        if self.ret is not None:
            # Store the closure ptr in the result temporary.
            asm.append(
                f"mov {self.ret.to_nasm_val(ctx)}, rax"
            )

        return asm


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
class FnDef(ToTgt):
    label: Label
    param: Temp = field(default_factory=param_factory(PARAM_ID))
    env: Temp = field(default_factory=param_factory(ENV_ID))
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

    def get_epilogue(self) -> List[str]:
        return [
            # Deallocate all the locals.
            f"leave",

            # After returning, deallocate the argument passed in.
            f"ret {self.param.size() + self.env.size()}"
        ]

    @ToTgt.annotate("FnDef")
    def to_nasm(self, ctx: gen_ctx.NasmGenCtx) -> List[str]:
        return [
            # Emit the label at the top of the function.
            *self.label.as_instr().to_nasm(ctx),

            # Allocate space for local variables.
            f"enter {self.local_alloca_size()}, 0"
        ] + [
            line  # Python's ugly flatmap...
            for instr in self.body
            for line in instr.to_nasm(ctx)
        ] + [
            *self.get_epilogue()
        ]

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

    def to_nasm(self, ctx: gen_ctx.NasmGenCtx) -> List[str]:
        return [f";;; {self.text}"]


@dataclass
class IfFalse(Instr):
    cond: Temp64
    label: Label

    @ToTgt.annotate("IfFalse")
    def to_nasm(self, ctx: gen_ctx.NasmGenCtx) -> List[str]:
        return [
            f"mov rax, {self.cond.to_nasm_val(ctx)}",
            f"test al, al",
            f"je {self.label.as_value().to_nasm_val(ctx)}",
        ]


@dataclass
class Goto(Instr):
    label: Label

    @ToTgt.annotate("Goto")
    def to_nasm(self, ctx: gen_ctx.NasmGenCtx) -> List[str]:
        return [
            f"jmp {self.label.as_value().to_nasm_val(ctx)}"
        ]


@dataclass
class Return(Instr):
    value: Value

    @ToTgt.annotate("Return")
    def to_nasm(self, ctx: gen_ctx.NasmGenCtx) -> List[str]:
        return [
            f"mov rax, {self.value.to_nasm_val(ctx)}",
        ] + [
            *ctx.get_epilogue()
        ]

