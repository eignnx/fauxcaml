from fauxcaml import build
from fauxcaml.lir import gen_ctx, lir, intrinsics


@build.name_asm_file(__file__)
def test_create_closure():
    ctx = gen_ctx.NasmGenCtx()

    with ctx.new_fn_def("my_closure") as (fn_lbl, param):
        ctx.add_instrs([
            lir.Comment(">>> Inside closure"),
            intrinsics.Add(param, lir.I64(100))
        ])

    closure_tmp = ctx.new_temp64()
    ret = ctx.new_temp64()

    ctx.add_instrs([
        lir.CreateClosure(fn_lbl.as_value(), [], closure_tmp),
        lir.CallClosure(closure_tmp, lir.I64(11), ret),
        lir.Return(ret),
    ])

    assert build.exit_code_for(ctx) == 111


@build.name_asm_file(__file__)
def test_adder_factory():
    ctx = gen_ctx.NasmGenCtx()

    with ctx.new_fn_def("$adder$closure") as (adder_closure_lbl, y):
        x = ctx.new_temp64()
        ctx.add_instrs([
            lir.EnvLookup(0, x),
            intrinsics.Add(x, y)
        ])

    with ctx.new_fn_def("$adder") as (adder_lbl, x):
        ret = ctx.new_temp64()
        ctx.add_instrs([
            lir.CreateClosure(adder_closure_lbl, [x], ret),
            lir.Return(ret),
        ])

    # Inside `main`:
    adder = ctx.new_temp64()
    plus77 = ctx.new_temp64()
    ret = ctx.new_temp64()

    ctx.add_instrs([
        lir.CreateClosure(adder_lbl, [], adder),
        lir.CallClosure(adder, lir.I64(77), plus77),
        lir.CallClosure(plus77, lir.I64(99), ret),
        lir.Return(ret),
    ])

    assert build.exit_code_for(ctx) == 77 + 99


@build.name_asm_file(__file__)
def test_arithmetic_intrinsics():
    ctx = gen_ctx.NasmGenCtx()

    expected = 2 * (9 // 2 - 7 % 3)

    t0 = ctx.new_temp64()
    t1 = ctx.new_temp64()
    t2 = ctx.new_temp64()
    ret = ctx.new_temp64()

    ctx.add_instrs([
        intrinsics.Div(lir.I64(9), lir.I64(2), t0),
        intrinsics.Mod(lir.I64(7), lir.I64(3), t1),
        intrinsics.Sub(t0, t1, t2),
        intrinsics.Mul(lir.I64(2), t2, ret),
        lir.Return(ret),
    ])

    assert build.exit_code_for(ctx) == expected


@build.name_asm_file(__file__)
def test_recursive_factorial():
    ctx = gen_ctx.NasmGenCtx()

    with ctx.new_fn_def("fact") as (fact_lbl, n):
        ret = ctx.new_temp64()
        cond = ctx.new_temp64()
        fact_rec = ctx.new_temp64()
        t0 = ctx.new_temp64()
        t1 = ctx.new_temp64()
        t2 = ctx.new_temp64()
        else_block = ctx.new_label("else_block")
        end_block = ctx.new_label("end_block")

        ctx.add_instrs([
            intrinsics.EqI64(n, lir.I64(0), cond),
            lir.IfFalse(cond, else_block),
            *[
                lir.Assign(ret, lir.I64(1)),
                lir.Goto(end_block),
            ],
            else_block.as_instr(),
            *[
                intrinsics.Sub(n, lir.I64(1), t0),
                lir.EnvLookup(lir.EnvLookup.RECURSIVE_IDX, fact_rec),
                lir.CallClosure(fact_rec, t0, t1),
                intrinsics.Mul(n, t1, t2),
                lir.Assign(ret, t2),
            ],
            end_block.as_instr(),
            lir.Return(ret),
        ])

    fact = ctx.new_temp64()
    t0 = ctx.new_temp64()

    ctx.add_instrs([
        lir.CreateClosure(fact_lbl, [], fact, recursive=True),
        lir.CallClosure(fact, lir.I64(5), t0),
        lir.Return(t0)
    ])

    assert build.exit_code_for(ctx) == 120


@build.name_asm_file(__file__)
def test_iterative_factorial():
    ctx = gen_ctx.NasmGenCtx()

    with ctx.new_fn_def("$iter") as (iter_lbl, tup):
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
            lir.GetElementPtr(tup, index=0, stride=8, res=i),
            lir.GetElementPtr(tup, index=1, stride=8, res=acc),
            lir.EnvLookup(lir.EnvLookup.RECURSIVE_IDX, env_n),
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

    with ctx.new_fn_def("$fact") as (fact_lbl, n):
        iter = ctx.new_temp64()
        tup = ctx.new_temp64()
        t1 = ctx.new_temp64()
        ctx.add_instrs([
            lir.CreateClosure(iter_lbl, [n], ret=iter, recursive=True),
            intrinsics.CreateTuple([lir.I64(1), lir.I64(1)], tup),
            lir.CallClosure(iter, tup, t1),
            lir.Return(t1),
        ])

    fact = ctx.new_temp64()
    t0 = ctx.new_temp64()

    ctx.add_instrs([
        lir.CreateClosure(fact_lbl, [], fact),
        lir.CallClosure(fact, lir.I64(5), t0),
        lir.Return(t0)
    ])

    assert build.exit_code_for(ctx) == 120


@build.name_asm_file(__file__)
def test_exit_intrinsic():
    ctx = gen_ctx.NasmGenCtx()

    t1 = ctx.new_temp64()

    ctx.add_instrs([
        intrinsics.Add(lir.I64(55), lir.I64(45), t1),
        intrinsics.Exit(t1),
        lir.Return(lir.I64(77)),
    ])

    assert build.exit_code_for(ctx) == 100

