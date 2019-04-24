from __future__ import annotations

import contextlib
import os
from typing import List, Optional, Dict

from fauxcaml.lir import lir


class NasmGenCtx:
    def __init__(self):
        self.next_label_id = 0
        self.statics: List[lir.Static] = []
        self.captured_names: Dict[str, int] = dict()
        self.local_names: Dict[str, lir.Value] = dict()
        self.main_fn_def: Optional[lir.FnDef] = self.create_main_fn_def()
        self.main_local_names = self.local_names
        self.current_fn: Optional[lir.FnDef] = self.main_fn_def
        self.fns: List[lir.FnDef] = [self.current_fn]

    def create_main_fn_def(self):
        lbl = self.new_label("main")  # NOTE: This must be exactly "main" for gcc.
        param = lir.Temp0()
        env = lir.Temp0()
        return lir.FnDef(lbl, param, env)

    def add_instr(self, instr: lir.Instr):
        self.current_fn.body.append(instr)

    def add_instrs(self, instrs: List[lir.Instr]):
        self.current_fn.body.extend(instrs)

    def new_label(self, custom_name: Optional[str] = None) -> lir.Label:
        label = lir.Label(self.next_label_id, custom_name)
        self.next_label_id += 1
        return label

    def new_temp64(self) -> lir.Temp64:
        return self.current_fn.new_temp64()

    @contextlib.contextmanager
    def inside_main(self):
        # READER BE AWARE: `a, b = b, a` indicates a swap.
        self.current_fn, old_fn_def = self.main_fn_def, self.current_fn
        self.local_names, old_local_names = self.main_local_names, self.local_names
        self.captured_names, old_captured_names = {}, self.captured_names
        yield
        self.captured_names = old_captured_names
        self.local_names = old_local_names
        self.current_fn = old_fn_def

    @contextlib.contextmanager
    def new_prelude_fn_def(
            self,
            fn_name: str,
            fn_lbl_name: Optional[str] = None,
            recursive: bool = False
    ):
        with self.new_fn_def(fn_lbl_name) as (lbl, param):
            yield (lbl, param)

        with self.inside_main():
            closure_temp = self.new_temp64()
            self.local_names[fn_name] = closure_temp
            self.main_fn_def.body.append(
                lir.CreateClosure(
                    fn_lbl=lbl,
                    captures=[],
                    ret=closure_temp,
                    recursive=recursive
                )
            )

    @contextlib.contextmanager
    def new_fn_def(
            self,
            custom_fn_name: Optional[str] = None,
            captures: Dict[str, int] = None
    ):
        captures = dict() if captures is None else captures
        new_fn_label = self.new_label(custom_fn_name)

        # READER BE AWARE: `a, b = b, a` indicates a swap.
        self.current_fn, old_fn_def = lir.FnDef(new_fn_label), self.current_fn
        self.local_names, old_local_names = dict(), self.local_names
        self.captured_names, old_captured_names = captures, self.captured_names

        self.fns.append(self.current_fn)

        yield (new_fn_label, self.current_fn.param)

        self.captured_names = old_captured_names
        self.local_names = old_local_names
        self.current_fn = old_fn_def

    def __str__(self) -> str:
        asm = []
        self.emit_exports(asm)
        self.emit_data_section(asm)
        self.emit_text_section(asm)
        return "\n".join(asm)

    def emit_exports(self, asm):
        asm += [
            "extern malloc",
            "extern printf",
            "global main",
        ]

        asm.append("")

    def emit_data_section(self, asm):
        asm.append("section .data")

        for static in self.statics:
            asm.append("    " + static.to_nasm_val(self))

        asm.append("")

    def emit_text_section(self, asm):
        asm.append("section .text")

        for fn_def in self.fns:
            self.current_fn = fn_def
            asm.append("")
            for line in fn_def.to_nasm(self):
                asm.append(line)

    def write_to_file(self, filename="./out.asm"):
        asm = str(self)
        basename = os.path.dirname(filename)
        os.makedirs(basename, exist_ok=True)
        with open(filename, "w+") as out:
            out.write(asm)

    def offset_of(self, temp: lir.Temp64):
        return self.current_fn.temporaries[temp]

    def get_epilogue(self) -> List[str]:
        return self.current_fn.get_epilogue()

    @contextlib.contextmanager
    def annotation(self, tag_name, **attrs):
        props = "".join(
            f" {prop}=\"{eval(expr, globals())}\""
            for prop, expr in attrs.items()
        )

        start_tag = f"<{tag_name}{props}>"
        end_tag = f"<{tag_name}>"
        self.add_instr(lir.Comment(start_tag, prefix=" "))
        yield
        self.add_instr(lir.Comment(end_tag, prefix=" "))
