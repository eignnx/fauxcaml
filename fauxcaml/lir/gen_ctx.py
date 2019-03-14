from __future__ import annotations

import contextlib
from typing import List, Optional

from fauxcaml.lir import lir


class NasmGenCtx:
    def __init__(self):
        self.next_label_id = 0
        self.statics: List[lir.Static] = []
        self.current_fn: lir.FnDef = self.create_main_fn_def()
        self.fns: List[lir.FnDef] = [self.current_fn]

    def create_main_fn_def(self):
        lbl = self.new_label("main")
        param = lir.Temp0()
        return lir.FnDef(lbl, param)

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
    def inside_new_fn_def(self, custom_fn_name=""):
        old_fn_def = self.current_fn
        new_fn_label = self.new_label(custom_fn_name)
        self.current_fn = lir.FnDef(new_fn_label)
        self.fns.append(self.current_fn)
        yield (new_fn_label, self.current_fn.param)
        self.current_fn = old_fn_def

    def __str__(self) -> str:
        asm = []
        self.emit_exports(asm)
        self.emit_data_section(asm)
        self.emit_text_section(asm)
        return "\n".join(asm)

    def write_to_file(self, filename="./out.asm"):
        asm = str(self)
        with open(filename, "w") as out:
            out.write(asm)

    def offset_of(self, temp: lir.Temp64):
        return self.current_fn.locals[temp]

    def emit_data_section(self, asm):
        asm.append("section .data")

        for static in self.statics:
            asm.append(static.to_nasm(self))

    def emit_exports(self, asm):
        asm += [
            "extern malloc",
            "global main",
        ]

    def emit_text_section(self, asm):
        asm.append("section .text")

        for fn_def in self.fns:
            self.current_fn = fn_def
            asm.append("")
            asm.append(fn_def.to_nasm(self))

    def get_epilogue(self) -> str:
        return "\n".join([
            # Deallocate all the locals.
            f"leave",

            # After returning, deallocate the argument passed in.
            f"ret {self.current_fn.param.size()}"
        ])
