from __future__ import annotations

import functools
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional, List, ClassVar, Dict, Union

from fauxcaml.lir import gen_ctx


class ToTgt(ABC):

    @abstractmethod
    def to_nasm(self, ctx: gen_ctx.NasmGenCtx) -> List[str]:
        pass

    ANNOTATION_INDENT = 4

    @staticmethod
    def annotate(tag, **attrs):
        """
        A decorator to put on top of `to_nasm` definitions. Will wrap the output
        nasm code with opening and closing tag comments. Attributes to print
        inside the tag can be passed in as key-value pairs where the key will
        be printed as-is, and the value will be evaluated in the context of
        the `self` method parameter.

        Ex:
            @ToTgt.annotate("MyInstruction", foo="foo_field", bar="1+2")
            def my_method(self, ...):
                ...

            ...will be printed as...

            <MyInstruction foo="value of self.foo_field" bar="3">
                ...
            </MyInstruction>

        """
        indent = " " * ToTgt.ANNOTATION_INDENT

        def decorator(f):
            @functools.wraps(f)
            def new_f(self, *args, **kwargs):

                props = "".join(
                    f" {prop}=\"{eval(expr, globals(), self.__dict__)}\""
                    for prop, expr in attrs.items()
                )

                return [
                    f"; <{tag}{props}>",
                    *(
                        f"{indent}{line}"
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
class Static(Value, ABC):
    pass


@dataclass
class StaticByteArray(Static):
    label: Label
    components: List[Union[str, int]]

    @staticmethod
    def mapper(comp: Union[str, int]):
        if type(comp) is int:
            return f"0x{comp:x}"  # Format in hex.
        elif type(comp) is str:
            return repr(comp)  # Put in quotes.

    def to_nasm_val(self, ctx: gen_ctx.NasmGenCtx) -> str:
        comps = ", ".join(self.mapper(comp) for comp in self.components)
        lbl = self.label.as_value().to_nasm_val(ctx)
        return f"{lbl} db {comps}"


class Instr(ToTgt, ABC):
    pass


@dataclass
class Nasm(Instr):
    description: str
    lines: List[str]

    @ToTgt.annotate("Nasm", description="description")
    def to_nasm(self, ctx: gen_ctx.NasmGenCtx) -> List[str]:
        return self.lines


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
    res: Temp64

    @ToTgt.annotate("GetElementPtr", stride="stride")
    def to_nasm(self, ctx: gen_ctx.NasmGenCtx) -> List[str]:
        if self.ptr.size() == 0:
            raise ValueError("Cannot perform GetElementPtr on zero-sized temporary!")

        offset = self.stride * self.index
        return [
            f"mov rax, {self.ptr.to_nasm_val(ctx)}",
            f"mov rax, [rax{offset:+}]",
            f"mov {self.res.to_nasm_val(ctx)}, rax",
        ]


@dataclass
class SetElementPtr(Instr):
    ptr: Temp64
    index: int
    stride: int
    value: Value

    @ToTgt.annotate("SetElementPtr", stride="stride")
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
    res: Temp64
    name: Optional[str] = None  # The name that is being looked up.

    RECURSIVE_INDEX: ClassVar[int] = 0

    @ToTgt.annotate("EnvLookup", name="name if name else ''", index="index")
    def to_nasm(self, ctx: gen_ctx.NasmGenCtx) -> List[str]:
        return GetElementPtr(
            ptr=ctx.current_fn.env,

            # Skip the fn ptr (label).
            # Note: The *fn ptr* is different from the *closure pointer* (which
            #       would be used when making a recursive call).
            index=self.index + 1,

            # Assumes all env elements are 8 bytes.
            stride=8,
            res=self.res
        ).to_nasm(ctx)


@dataclass
class CallClosure(Instr):
    fn: Temp64
    arg: Value
    ret: Temp  # If `Temp0`, no return value (Unit)

    @ToTgt.annotate("CallClosure")
    def to_nasm(self, ctx: gen_ctx.NasmGenCtx) -> List[str]:
        return [
            f"mov rax, {self.fn.to_nasm_val(ctx)}",
            f"push rax",
            f"push {self.arg.to_nasm_val(ctx)}",
            f"call [rax]",
        ] + ([
            f"mov {self.ret.to_nasm_val(ctx)}, rax"
        ] if self.ret.size() > 0 else [])


@dataclass
class CreateClosure(Instr):
    fn_lbl: Label

    # It is the creator's responsibility to generate the code that provides these values. This may require
    # environment lookups.
    captures: List[Value]

    ret: Temp64
    recursive: bool = False

    @ToTgt.annotate("CreateClosure", recursive="recursive")
    def to_nasm(self, ctx: gen_ctx.NasmGenCtx) -> List[str]:

        # The size of a closure is the sum of the sizes of the captured
        # variables and the size of the 8-byte label (function pointer).
        # If the closure is recursive, a pointer to the closure struct
        # itself must also be stored.
        size = self.fn_lbl.as_value().size()              \
             + sum(val.size() for val in self.captures)   \
             + (self.ret.size() if self.recursive else 0)

        asm = [
            # Allocate a `size`-sized block of memory on the heap.
            f"mov rdi, {size}",
            f"call malloc",
            f"mov r8, rax",

            # Store the label (fn ptr) in the first position
            f"mov QWORD [r8], {self.fn_lbl.as_value().to_nasm_val(ctx)}",
        ]

        # Setup an offset into the closure struct. Will be incremented AFTER
        # the value is put into the struct.
        offset = self.fn_lbl.as_value().size()  # Skip stored fn label.

        # If the function is recursive, the pointer to the closure must be
        # stored in the environment.
        if self.recursive:
            asm.append(
                f"mov [r8{offset:+}], r8 ; Store recursive pointer to closure."
            )
            offset += 8

        if self.captures:
            asm.append("; <ConstructEnvironment>")

            for val in self.captures:
                asm += [
                    # Get each captured value, put in `rax.`
                    f"mov rax, {val.to_nasm_val(ctx)} ; Get the captured value, put in `rax`.",

                    # Store the captured value in the closure struct.
                    f"mov QWORD [r8{offset:+}], rax ; Store the captured value in the closure struct.",
                ]

                # Increment the offset by the size of the thing that was stored.
                offset += val.size()

            asm.append("; </ConstructEnvironment>")

        asm.append(
            # Store the closure ptr in the result temporary.
            f"mov {self.ret.to_nasm_val(ctx)}, r8",
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

    temporaries: Dict[Temp, int] = field(default_factory=dict)
    current_offset: int = 0  # Base ptr and return addr stored first
    next_temp_id: int = 0

    def __post_init__(self):
        # The param is always located 16 bytes above [rbp], and the env ptr
        # is 24 bytes above [rbp].
        self.temporaries[self.param] = +16
        self.temporaries[self.env] = +24

    def local_alloca_size(self) -> int:
        return sum(
            local.size() for local in self.temporaries.keys()
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
        self.temporaries[t] = self.current_offset
        return t


@dataclass
class Comment(Instr):
    text: str
    prefix: str = ";; "

    def to_nasm(self, ctx: gen_ctx.NasmGenCtx) -> List[str]:
        return [
            f";{self.prefix}{self.text}",
        ]


@dataclass
class IfFalse(Instr):
    cond: Value
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
        return ([
            f"mov rax, {self.value.to_nasm_val(ctx)}",
        ] if self.value.SIZE > 0 else [
            f"xor rax, rax ; Zero out `rax`.",
        ]) + [
            *ctx.get_epilogue()
        ]


@dataclass
class Assign(Instr):
    lhs: Temp
    rhs: Value

    @ToTgt.annotate("Assign")
    def to_nasm(self, ctx: gen_ctx.NasmGenCtx) -> List[str]:
        return [
            f"mov rax, {self.rhs.to_nasm_val(ctx)}",
            f"mov {self.lhs.to_nasm_val(ctx)}, rax",
        ]
