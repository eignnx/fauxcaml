from __future__ import annotations

import functools
import typing
from abc import ABC, abstractmethod
from dataclasses import dataclass

from fauxcaml.lir import gen_ctx, lir, intrinsics
from fauxcaml.semantics import check
from fauxcaml.semantics import typ
from fauxcaml.semantics import unifier_set


class AstNode(ABC):
    def __init__(self):
        self._type: typing.Optional[typ.Type] = None
        self._unifiers: typing.Optional[unifier_set.UnifierSet] = None

    @abstractmethod
    def infer_type(self, checker: check.Checker) -> typ.Type:
        pass

    # @abstractmethod
    def to_lir(self, ctx: gen_ctx.NasmGenCtx) -> lir.Value:
        pass

    # @abstractmethod
    # def code_gen(self, ctx: gen_ctx.CodeGenContext) -> hir.Value:
    #     pass

    @staticmethod
    def cache_type(fn: typing.Callable[[AstNode, check.Checker], typ.Type]):
        """
        Decorator for use on `AstNode.infer_type`. It stores the return value
        of `infer_type` in the field `self._type`, and stores the `Checker`'s
        unifier set under `self._unifiers` so that when the property
        `self.type` is accessed, `self` can lookup the (potentially non-
        concretized) type with `self._unifiers.concretize`.
        """
        @functools.wraps(fn)
        def new_fn(self, checker: check.Checker) -> typ.Type:

            # First initialize the `_unifier` field. This is necessary for
            # `syntax.Const` objects' `infer_type` method, which immediately
            # calls the `self.type` property.
            self._unifiers = checker.unifiers

            # Now call the wrapped function.
            ret = fn(self, checker)

            # Then cache the returned value.
            self._type = ret

            # Finally, actually return it so we maintain the interface.
            return ret

        return new_fn

    @property
    def type(self) -> typ.Type:
        """
        Returns the cached type inferred for this ast node. Must be called
        AFTER calling `infer_type` on the instance.
        """
        if self._type is not None and self._unifiers is not None:
            return self._unifiers.concretize(self._type)
        else:
            cls = self.__class__.__name__
            msg = f"The attribute {cls}.type is not initialized until after " \
                  f"calling {cls}.infer_type!"
            raise AttributeError(msg)


class Value(AstNode, ABC):
    pass


@dataclass(eq=True)
class Ident(Value):
    """
    An identifier.
    x, printf, abstract_singleton_bean
    """
    name: str

    @AstNode.cache_type
    def infer_type(self, checker: check.Checker) -> typ.Type:
        return checker.duplicate_type(checker.type_env[self])

    def to_lir(self, ctx: gen_ctx.NasmGenCtx) -> lir.Value:
        return ctx.local_names[self.name]

    # def code_gen(self, ctx: gen_ctx.CodeGenContext) -> hir.Value:
    #     return hir.Ident(self.name, self.type)

    def __str__(self):
        return self.name

    def __hash__(self):
        return hash(self.name)


@dataclass(eq=True)
class Const(Value):
    """
    A literal.
    1, true, -4.21983, point { x=1, y=2 }
    """
    value: object
    _type: typ.Type  # `_` ensures no collision with superclass property

    @AstNode.cache_type
    def infer_type(self, checker: check.Checker) -> typ.Type:
        return self.type  # Note: calls superclass property

    def to_lir(self, ctx: gen_ctx.NasmGenCtx) -> lir.Value:
        if self.type == typ.Int:
            assert isinstance(self.value, int)
            return lir.I64(self.value)
        raise NotImplementedError

    # def code_gen(self, ctx: gen_ctx.CodeGenContext) -> hir.Value:
    #     return hir.Const(self.value, self.type)

    def __str__(self):
        return str(self.value)


@dataclass(eq=True)
class Lambda(AstNode):
    """
    lambda param: body
    """
    param: Ident
    body: AstNode

    @AstNode.cache_type
    def infer_type(self, checker: check.Checker) -> typ.Type:

        # In a new scope, infer the type of the body.
        # Scoped because `self.param` is valid only inside this scope.
        # Parameter types are non-generic while checking the body.
        with checker.new_scope(), checker.scoped_non_generic() as arg_type:
            checker.type_env[self.param] = arg_type
            body_type = self.body.infer_type(checker)

        # After inferring body's type, arg type might be known.
        arg_type = checker.unifiers.concretize(arg_type)

        return typ.Fn(arg_type, body_type)

    # def code_gen(self, ctx: gen_ctx.CodeGenContext) -> hir.Value:
    #     with ctx.define_fn(self.param.name, self.type) as fn_label:
    #         self.body.code_gen(ctx)
    #     return fn_label


@dataclass(eq=True)
class Call(AstNode):
    """
    fn(arg)
    """
    fn: AstNode
    arg: AstNode

    @AstNode.cache_type
    def infer_type(self, checker: check.Checker) -> typ.Type:

        # Get best guess as to the type of `self.arg`.
        arg_type = self.arg.infer_type(checker)

        # Set up a function type.
        beta = checker.fresh_var()
        fn_type_joiner = typ.Fn(arg_type, beta)

        # Ensure the `self.fn` refers to a Fn type.
        fn_type = self.fn.infer_type(checker)

        checker.unify(fn_type, fn_type_joiner)

        # In case beta's root was changed in the last unification, get it's
        # current root.
        return checker.unifiers.concretize(beta)

    def to_lir(self, ctx: gen_ctx.NasmGenCtx) -> lir.Value:
        ret = ctx.new_temp64()
        if isinstance(self.fn, Ident):
            if self.fn.name == "exit":
                arg_tmp = self.arg.to_lir(ctx)
                ctx.add_instr(
                    intrinsics.Exit(arg_tmp)
                )
                return lir.Temp0()
            elif self.fn.name in ("+", "-", "*", "div", "mod"):
                instr = {
                    "+": intrinsics.AddSub,
                    "-": intrinsics.AddSub,
                    "*": intrinsics.MulDivMod,
                    "div": intrinsics.MulDivMod,
                    "mod": intrinsics.MulDivMod,
                }[self.fn.name]

                assert isinstance(self.arg, TupleLit)
                assert len(self.arg.vals) == 2
                arg1, arg2 = self.arg.vals
                ctx.add_instr(
                    instr(
                        self.fn.name,
                        arg1.to_lir(ctx),
                        arg2.to_lir(ctx),
                        ret,
                    )
                )
                return ret

            elif self.fn.name == "=":
                assert isinstance(self.arg, TupleLit)
                assert len(self.arg.vals) == 2
                arg1, arg2 = self.arg.vals
                ctx.add_instr(
                    intrinsics.EqI64(
                        arg1.to_lir(ctx),
                        arg2.to_lir(ctx),
                        ret,
                    )
                )
                return ret
        arg_tmp = self.arg.to_lir(ctx)
        fn_tmp = self.fn.to_lir(ctx)
        if not isinstance(fn_tmp, lir.Temp64):
            msg = f"Cannot call something other than a 64-bit temporary as if it " \
                  f"were a closure! Given type '{type(fn_tmp)}'"
            raise ValueError(msg)
        ctx.add_instr(
            lir.CallClosure(
                typing.cast(lir.Temp64, fn_tmp),
                arg_tmp,
                ret
            )
        )
        return ret


# def code_gen(self, ctx: gen_ctx.CodeGenContext) -> hir.Value:
    #
    #     # Generate code for function and arg.
    #     fn_id = self.fn.code_gen(ctx)
    #     arg_tmp = self.arg.code_gen(ctx)
    #
    #     # Create a new temporary for the return value.
    #     ret = ctx.new_temp(self.type)
    #
    #     # Generate code for the call.
    #     ctx.emit(hir.Call(ret, fn_id, arg_tmp))
    #     return ret


@dataclass(eq=True)
class If(AstNode):
    """
    if pred then yes else no
    """
    pred: AstNode
    yes: AstNode
    no: AstNode

    @AstNode.cache_type
    def infer_type(self, checker: check.Checker) -> typ.Type:
        pred_type = self.pred.infer_type(checker)
        checker.unify(pred_type, typ.Bool)

        yes_type = self.yes.infer_type(checker)
        no_type = self.no.infer_type(checker)
        checker.unify(yes_type, no_type)

        return checker.unifiers.concretize(yes_type)

    # def code_gen(self, ctx: gen_ctx.CodeGenContext) -> hir.Value:
    #
    #     # Setup a temporary for the return value of the expression.
    #     ret = ctx.new_temp(self.type)
    #
    #     # Generate code for predicate.
    #     pred_tmp = self.pred.code_gen(ctx)
    #
    #     # Make two new labels.
    #     else_lbl = ctx.new_label()
    #     end_lbl = ctx.new_label()
    #
    #     # Emit the conditional jump instr.
    #     ctx.emit(hir.IfFalse(pred_tmp, else_lbl))
    #
    #     # Generate the yes branch, then add a "goto end".
    #     yes_ret = self.yes.code_gen(ctx)
    #     ctx.emit(hir.Store(ret, yes_ret))
    #     ctx.emit(hir.Goto(end_lbl))
    #
    #     # Generate the else branch
    #     ctx.emit(else_lbl)
    #     no_ret = self.no.code_gen(ctx)
    #     ctx.emit(hir.Store(ret, no_ret))
    #
    #     # Specify the end of the if statement
    #     ctx.emit(end_lbl)
    #
    #     return ret


@dataclass(eq=True)
class Let(AstNode):
    """
    let left = right in body
    """
    left: Ident
    right: AstNode
    body: AstNode

    @AstNode.cache_type
    def infer_type(self, checker: check.Checker) -> typ.Type:

        # Scope the `left = right` binding.
        with checker.new_scope():

            # First, bind `left` to a fresh type variable. This allows
            # for recursive let statements.
            # Note: `alpha` is only non-generic while inferring `right`. TODO: Why tho?
            with checker.scoped_non_generic() as alpha:
                checker.type_env[self.left] = alpha

                # HACK: Do this so that `Ident` `self.left` caches its type.
                _ = self.left.infer_type(checker)

                # Next infer the type of `right` using the binding just created.
                right_type = self.right.infer_type(checker)

            # Link the type variable with the inferred type of `right`.
            checker.unify(alpha, right_type)

            # With the environment set up, now the body can be typechecked.
            return self.body.infer_type(checker)

    def to_lir(self, ctx: gen_ctx.NasmGenCtx) -> lir.Temp:
        if isinstance(self.right, Lambda):

            with ctx.inside_new_fn_def(self.left.name) as (lbl, param_tmp):
                param_name = self.right.param.name
                ctx.local_names[param_name] = param_tmp
                self.right.body.to_lir(ctx)

            ctx.add_instr(
                lir.CreateClosure(
                    fn_lbl=lbl,
                    captures=[],
                    ret=ctx.local_names[self.left.name],
                )
            )
        else:
            tmp: lir.Temp = self.right.to_lir(ctx)
            ctx.local_names[self.left.name] = tmp

        return lir.Temp0()

    # def code_gen(self, ctx: gen_ctx.CodeGenContext) -> hir.Value:
    #
    #     # First generate the right hand side of the binding.
    #     right_tmp = self.right.code_gen(ctx)
    #     left_tmp = self.left.code_gen(ctx)
    #     left_tmp = typing.cast(hir.Ident, left_tmp)  # Cast to `hir.Ident` from `hir.Value`.
    #
    #     # Emit the binding `left = right`.
    #     ctx.emit(hir.Store(left_tmp, right_tmp))
    #
    #     ret = ctx.new_temp(self.type)  # TODO: Optimize this away? Only need one return temporary?
    #
    #     # Generate code for the body, then save the result in ret.
    #     body_tmp = self.body.code_gen(ctx)
    #     ctx.emit(hir.Store(ret, body_tmp))
    #
    #     return ret


@dataclass(eq=True)
class TupleLit(AstNode):
    vals: typing.Tuple[AstNode, ...]

    def __init__(self, *vals):
        super().__init__()
        self.vals = vals

    def infer_type(self, checker: check.Checker) -> typ.Type:
        components = (v.infer_type(checker) for v in self.vals)
        return typ.Tuple(*components)

    def to_lir(self, ctx: gen_ctx.NasmGenCtx) -> lir.Temp:
        res = ctx.new_temp64()

        tmps = filter(
            lambda v: type(v) is not lir.Temp0,  # Skip all Unit values (if any).
            (v.to_lir(ctx) for v in self.vals)
        )

        ctx.add_instr(
            intrinsics.CreateTuple(list(tmps), res)
        )

        return res

    # def code_gen(self, ctx: gen_ctx.CodeGenContext) -> hir.Value:
    #     raise NotImplementedError


@dataclass
class LetStmt(AstNode):
    """
    Represents a top-level let statement.
    ```
    let f x =
        x + 1;;
    ```
    """
    left: Ident
    right: AstNode

    @AstNode.cache_type
    def infer_type(self, checker: check.Checker) -> typ.Type:

        # First, bind `left` to a fresh type variable. This allows
        # for recursive let statements.
        # Note: `alpha` is only non-generic while inferring `right`. TODO: Why tho?
        with checker.scoped_non_generic() as alpha:
            checker.type_env[self.left] = alpha

            # HACK: Do this so that `Ident` `self.left` caches its type.
            _ = self.left.infer_type(checker)

            # Next infer the type of `right` using the binding just created.
            right_type = self.right.infer_type(checker)

        # Link the type variable with the inferred type of `right`.
        checker.unify(alpha, right_type)

        return typ.Unit

    def to_lir(self, ctx: gen_ctx.NasmGenCtx) -> lir.Temp:
        if isinstance(self.right, Lambda):

            with ctx.inside_new_fn_def(self.left.name) as (lbl, param_tmp):
                param_name = self.right.param.name
                ctx.local_names[param_name] = param_tmp
                self.right.body.to_lir(ctx)

            ctx.add_instr(
                lir.CreateClosure(
                    fn_lbl=lbl,
                    captures=[],
                    ret=ctx.local_names[self.left.name],
                )
            )
        else:
            val = self.right.to_lir(ctx)
            ctx.local_names[self.left.name] = val

        return lir.Temp0()


@dataclass
class TopLevelStmts(AstNode):
    stmts: typing.List[AstNode]

    @AstNode.cache_type
    def infer_type(self, checker: check.Checker) -> typ.Type:
        for stmt in self.stmts:
            stmt.infer_type(checker)
        return typ.Unit

    def to_lir(self, ctx: gen_ctx.NasmGenCtx) -> lir.Temp:
        for stmt in self.stmts:
            stmt.to_lir(ctx)
        return lir.Temp0()

    def __add__(self, other):
        return TopLevelStmts(self.stmts + other.stmts)

