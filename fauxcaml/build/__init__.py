import contextlib
import functools
import os
import subprocess
from typing import Callable

from lir import gen_ctx

ASM_FILE_NAME = "/tmp/fauxcaml.asm"
OBJ_FILE_NAME = "/tmp/fauxcaml.o"
EXE_FILE_NAME = "/tmp/fauxcaml"


def set_out_file_names(name):
    global ASM_FILE_NAME, OBJ_FILE_NAME, EXE_FILE_NAME
    ASM_FILE_NAME = f"/tmp/{name}.asm"
    OBJ_FILE_NAME = f"/tmp/{name}.o"
    EXE_FILE_NAME = f"/tmp/{name}"


@contextlib.contextmanager
def tmp_asm_files_named(f_name):
    global ASM_FILE_NAME, OBJ_FILE_NAME, EXE_FILE_NAME
    old_paths = (ASM_FILE_NAME, OBJ_FILE_NAME, EXE_FILE_NAME)
    set_out_file_names(f_name)
    yield
    (ASM_FILE_NAME, OBJ_FILE_NAME, EXE_FILE_NAME) = old_paths


def name_asm_file(module_path: str = "TEST"):
    base_name = os.path.basename(os.path.splitext(module_path)[0])

    def decorator(f: Callable):
        f_name = f"{base_name}.{f.__qualname__}"

        @functools.wraps(f)
        def new_f():
            with tmp_asm_files_named(f_name):
                f()

        return new_f
    return decorator


def assemble(ctx, f_in=None, f_out=None):
    f_in = ASM_FILE_NAME if f_in is None else f_in
    f_out = OBJ_FILE_NAME if f_out is None else f_out
    ctx.write_to_file(f_in)
    cmd = f"nasm -f elf64 {f_in} -o {f_out}"
    return subprocess.run(cmd.split())


def link(f_in=None, f_out=None):
    f_in = OBJ_FILE_NAME if f_in is None else f_in
    f_out = EXE_FILE_NAME if f_out is None else f_out
    cmd = f"gcc {f_in} -o {f_out}"
    return subprocess.run(cmd.split())


def run(exe_name=None):
    exe_name = EXE_FILE_NAME if exe_name is None else exe_name
    return subprocess.run([exe_name])


def assert_assembles(ctx: gen_ctx.NasmGenCtx):
    assert assemble(ctx).returncode == 0, "Failed to assemble with nasm!"


def assert_main_returns(ctx: gen_ctx.NasmGenCtx, expected_ret_code=0):
    """
    Generates assembly, assembles, links, and runs the program. Checks that
    the actual program's return code matches the expected return code.
    """
    ctx.write_to_file(ASM_FILE_NAME)
    assert assemble(ctx).returncode == 0, "Failed to assemble with nasm!"
    assert link().returncode == 0, "Failed to link with gcc!"
    actual_ret_code = run().returncode
    # Note: a unix process can only return one byte!
    assert actual_ret_code == (expected_ret_code % 256)

    if actual_ret_code != expected_ret_code:
        import sys
        print(
            "\nWARNING: actual return code is congruent to expected return code "
            "mod 256, but is not equivalent!",
            file=sys.stderr
        )

