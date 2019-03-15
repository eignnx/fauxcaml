import subprocess

import pytest

from fauxcaml.lir import gen_ctx, lir, intrinsics

ASM_FILE_NAME = "/tmp/fauxcaml.asm"
OBJ_FILE_NAME = "/tmp/fauxcaml.o"
EXE_FILE_NAME = "/tmp/fauxcaml"


def assemble(ctx, f_in=ASM_FILE_NAME, f_out=OBJ_FILE_NAME):
    ctx.write_to_file(f_in)
    cmd = f"nasm -f elf64 {f_in} -o {f_out}"
    return subprocess.run(cmd.split())


def link(f_in=OBJ_FILE_NAME, f_out=EXE_FILE_NAME):
    cmd = f"gcc {f_in} -o {f_out}"
    return subprocess.run(cmd.split())


def run(exe_name=EXE_FILE_NAME):
    return subprocess.run([exe_name])


def assert_assembles(ctx: gen_ctx.NasmGenCtx):
    assert assemble(ctx).returncode == 0, "Failed to assemble with nasm!"


def assert_main_returns(ctx, expected_ret_code=0):
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


def test_create_closure():
    ctx = gen_ctx.NasmGenCtx()

    with ctx.inside_new_fn_def("my_closure") as (fn_lbl, param):
        ctx.add_instrs([
            lir.Comment(">>> Inside closure"),
            intrinsics.Add(param, lir.I64(100))
        ])

    closure_tmp = ctx.new_temp64()

    ctx.add_instrs([
        lir.CreateClosure(fn_lbl.as_value(), [], closure_tmp),
        lir.CallClosure(closure_tmp, lir.I64(11))
    ])

    assert_main_returns(ctx, 111)


def test_adder_factory():
    ctx = gen_ctx.NasmGenCtx()

    with ctx.inside_new_fn_def("$adder$closure") as (adder_closure_lbl, y):
        x = ctx.new_temp64()
        ctx.add_instrs([
            lir.EnvLookup(0, x),
            intrinsics.Add(x, y)
        ])

    with ctx.inside_new_fn_def("$adder") as (adder_lbl, x):
        ctx.add_instr(
            lir.CreateClosure(
                adder_closure_lbl,
                [x]
            )
        )

    # Inside `main`:
    adder = ctx.new_temp64()
    plus77 = ctx.new_temp64()

    ctx.add_instrs([
        lir.CreateClosure(adder_lbl, [], adder),
        lir.CallClosure(adder, lir.I64(77), plus77),
        lir.CallClosure(plus77, lir.I64(99)),
    ])

    assert_main_returns(ctx, 77 + 99)


def test_arithmetic_intrinsics():
    ctx = gen_ctx.NasmGenCtx()

    expected = 2 * (9 // 2 - 7 % 3)

    t0 = ctx.new_temp64()
    t1 = ctx.new_temp64()
    t2 = ctx.new_temp64()

    ctx.add_instrs([
        intrinsics.Div(lir.I64(9), lir.I64(2), t0),
        intrinsics.Mod(lir.I64(7), lir.I64(3), t1),
        intrinsics.Sub(t0, t1, t2),
        intrinsics.Mul(lir.I64(2), t2)
    ])

    assert_main_returns(ctx, expected)


def test_iterative_fibonacci():
    ctx = gen_ctx.NasmGenCtx()

    with ctx.inside_new_fn_def("$iter") as (iter_lbl, tup):
        i = ctx.new_temp64()
        acc = ctx.new_temp64()
        env_n = ctx.new_temp64()
        cond = ctx.new_temp64()

        i_plus_1 = ctx.new_temp64()
        i_times_acc = ctx.new_temp64()
        env_iter = ctx.new_temp64()
        next_tup = ctx.new_temp64()

        ret = ctx.new_temp64()

        _else = ctx.new_label("_else")
        end_if = ctx.new_label("end_if")

        ctx.add_instrs([
            lir.GetElementPtr(tup, 0, 8, i),
            lir.GetElementPtr(tup, 1, 8, acc),
            lir.EnvLookup(0, env_n),
            intrinsics.EqI64(i, env_n, cond),
            lir.IfFalse(cond, _else),
            *[
                intrinsics.Mul(i, acc, ret),
                lir.Goto(end_if)
            ],
            _else.as_instr(),
            *[
                intrinsics.Add(i, lir.I64(1), i_plus_1),
                intrinsics.Mul(i, acc, i_times_acc),
                intrinsics.CreateTuple([i_plus_1, i_times_acc], next_tup),
                lir.EnvLookup(1, env_iter),
                lir.CallClosure(env_iter, next_tup, ret)
            ],
            end_if.as_instr(),
            lir.Return(ret)
        ])

    with ctx.inside_new_fn_def("$fact") as (fact_lbl, n):
        iter = ctx.new_temp64()
        t0 = ctx.new_temp64()
        t1 = ctx.new_temp64()
        ctx.add_instrs([
            lir.CreateClosure(iter_lbl, [n], iter, recursive=True),
            intrinsics.CreateTuple([
                lir.I64(0),
                lir.I64(1),
            ], t0),
            lir.CallClosure(iter, t0, t1),
            lir.Return(t1),
        ])

    fact = ctx.new_temp64()
    t0 = ctx.new_temp64()

    ctx.add_instrs([
        lir.CreateClosure(fact_lbl, [], fact),
        lir.CallClosure(fact, lir.I64(5), t0),
        lir.Return(t0)
    ])

    assert_main_returns(ctx, 120)



