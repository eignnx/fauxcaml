from __future__ import annotations

from typing import List

from fauxcaml.code_gen.ir import Instr


class BasicBlock:
    @staticmethod
    def identify_leaders(program: List[Instr]):
        ...
