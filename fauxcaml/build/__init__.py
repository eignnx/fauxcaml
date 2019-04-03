import contextlib
import functools
import os
import subprocess
import sys
from dataclasses import dataclass
from typing import Callable, Union, Optional

from fauxcaml import parsing
from fauxcaml.lir import gen_ctx
from fauxcaml.semantics import check

ASM_FILE_NAME = "/tmp/fauxcaml_tests/fauxcaml.asm"
OBJ_FILE_NAME = "/tmp/fauxcaml_tests/fauxcaml.o"
EXE_FILE_NAME = "/tmp/fauxcaml_tests/fauxcaml"


def set_out_file_names(name):
    global ASM_FILE_NAME, OBJ_FILE_NAME, EXE_FILE_NAME
    ASM_FILE_NAME = f"/tmp/fauxcaml_tests/{name}.asm"
    OBJ_FILE_NAME = f"/tmp/fauxcaml_tests/{name}.o"
    EXE_FILE_NAME = f"/tmp/fauxcaml_tests/{name}"


@contextlib.contextmanager
def tmp_asm_files_named(f_name):
    global ASM_FILE_NAME, OBJ_FILE_NAME, EXE_FILE_NAME
    old_paths = (ASM_FILE_NAME, OBJ_FILE_NAME, EXE_FILE_NAME)
    set_out_file_names(f_name)
    yield
    (ASM_FILE_NAME, OBJ_FILE_NAME, EXE_FILE_NAME) = old_paths


def name_asm_file(module_path):
    """
    A decorator to put on top of tests which create asm, obj, and exe files.
    Usually, you should pass `__file__` in as the module path.
    EX:
        @name_asm_file(__file__)
        def test_my_feature():
            ...
    """
    base_name = os.path.basename(os.path.splitext(module_path)[0])

    def decorator(f: Callable):
        f_name = f"{base_name}/{f.__name__}"

        @functools.wraps(f)
        def new_f():
            with tmp_asm_files_named(f_name):
                f()

        return new_f
    return decorator


def assemble(ctx, asm_file=None, obj_file=None):
    asm_file = ASM_FILE_NAME if asm_file is None else asm_file
    obj_file = OBJ_FILE_NAME if obj_file is None else obj_file
    ctx.write_to_file(asm_file)
    cmd = f"nasm -f elf64 {asm_file} -o {obj_file}"
    return subprocess.run(cmd.split())


def link(obj_file=None, exe_file=None):
    obj_file = OBJ_FILE_NAME if obj_file is None else obj_file
    exe_file = EXE_FILE_NAME if exe_file is None else exe_file
    cmd = f"gcc {obj_file} -o {exe_file}"
    return subprocess.run(cmd.split())


def run(exe_file=None):
    exe_file = EXE_FILE_NAME if exe_file is None else exe_file
    return subprocess.run([exe_file])


def assert_assembles(ctx: gen_ctx.NasmGenCtx):
    assert assemble(ctx).returncode == 0, "Failed to assemble with nasm!"


@dataclass(eq=False)
class ExitCodeResult:
    code: int

    def wraps(self) -> bool:
        return self.code % 256 != self.code

    def __str__(self):
        return str(self.code)

    def __eq__(self, other) -> bool:
        if isinstance(other, int):
            if (self.code % 256) == (other % 256):
                if self.wraps():
                    msg = (
                        "\n"
                        "WARNING: actual return code is congruent to expected "
                        "return code mod 256, but is not equivalent!"
                    )
                    print(msg, file=sys.stderr)
                return True
            else:
                return False


def compile_src(src_txt: str) -> gen_ctx.NasmGenCtx:
    checker = check.Checker()
    ctx = gen_ctx.NasmGenCtx()

    ast = parsing.parse(src_txt)
    ast.infer_type(checker)
    _ = ast.to_lir(ctx)
    return ctx


def exit_code_for(arg: Union[str, gen_ctx.NasmGenCtx]) -> ExitCodeResult:
    """
    Generates assembly, assembles, links, and runs the program.
    """
    if isinstance(arg, str):
        ctx = compile_src(arg)
    else:
        ctx = arg

    ctx.write_to_file(ASM_FILE_NAME)
    if assemble(ctx).returncode != 0:
        raise RuntimeError("Failed to assemble with nasm!")
    if link().returncode != 0:
        raise RuntimeError("Failed to link with gcc!")
    exit_code = run().returncode
    return ExitCodeResult(exit_code)


def compile_from_source_file(source_file: str, exe_file: Optional[str] = None):
    with open(source_file, "r") as f:
        ctx = compile_src(f.read())

    base_name = os.path.basename(os.path.splitext(source_file)[0])
    asm_file = f"./{base_name}.asm"
    obj_file = f"./{base_name}.o"
    exe_file = f"./{base_name}" if exe_file is None else exe_file
    if assemble(ctx, asm_file=asm_file, obj_file=obj_file).returncode != 0:
        raise RuntimeError("Failed to assemble with nasm!")
    if link(obj_file=obj_file, exe_file=exe_file).returncode != 0:
        raise RuntimeError("Failed to link with gcc!")
