from __future__ import annotations

import contextlib
import os
from typing import List, Optional, Dict

from fauxcaml.lir import lir


class NasmGenCtx:
    def __init__(self, generate_main=True):
        self.next_label_id = 0
        self.local_names: Dict[str, lir.Value] = dict()
        self.captured_names: Dict[str, int] = dict()
        self.statics: List[lir.Static] = []
        self.current_fn: lir.FnDef = self.create_main_fn_def() if generate_main else None
        self.fns: List[lir.FnDef] = [self.current_fn] if generate_main else []

    def create_main_fn_def(self):
        lbl = self.new_label("main")
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
    def new_fn_def(self, custom_fn_name: Optional[str] = None, recursive: bool = False):
        old_fn_def = self.current_fn
        new_fn_label = self.new_label(custom_fn_name)
        self.current_fn = lir.FnDef(new_fn_label)
        self.fns.append(self.current_fn)
        old_local_names = self.local_names
        self.local_names = dict()
        old_captured_names = self.captured_names
        self.captured_names = {  # TODO: Correct to forget about outer captures?
            custom_fn_name: lir.EnvLookup.RECURSIVE_IDX
        } if recursive else dict()

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

    def emit_data_section(self, asm):
        asm.append("section .data")

        # Define `printf`-style format string for printing integers.
        asm.append("$println_int_fmt db '%d', 0xa, 0x0")

        for static in self.statics:
            asm.append(static.to_nasm_val(self))  # Todo: These probably aren't values...

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
        return self.current_fn.locals[temp]

    def get_epilogue(self) -> List[str]:
        return self.current_fn.get_epilogue()
