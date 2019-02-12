from __future__ import annotations

import functools
import typing
from abc import ABC, abstractmethod
from dataclasses import dataclass

from fauxcaml.code_gen import gen_ctx
from fauxcaml.code_gen import ir
from fauxcaml.semantics import check
from fauxcaml.semantics import typ
from fauxcaml.semantics import unifier_set


class AstNode(ABC):
    def __init__(self):
        self._type: typ.Type = None
        self._unifiers: unifier_set.UnifierSet = None

    @abstractmethod
    def infer_type(self, checker: check.Checker) -> typ.Type:
        pass

    @abstractmethod
    def code_gen(self, ctx: gen_ctx.CodeGenContext) -> ir.Value:
        pass

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

    def code_gen(self, ctx: gen_ctx.CodeGenContext) -> ir.Value:
        return ir.Ident(self.name, self.type)

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

    def code_gen(self, ctx: gen_ctx.CodeGenContext) -> ir.Value:
        return ir.Const(self.value, self.type)

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

    def code_gen(self, ctx: gen_ctx.CodeGenContext) -> ir.Value:
        with ctx.define_fn(self.param.name, self.type) as fn_label:
            self.body.code_gen(ctx)
        return fn_label


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

    def code_gen(self, ctx: gen_ctx.CodeGenContext) -> ir.Value:

        # Generate code for function and arg.
        fn_label = typing.cast(ir.Label, self.fn.code_gen(ctx))
        arg_tmp = self.arg.code_gen(ctx)

        # Create a new temporary for the return value.
        ret = ctx.new_temp(self.type)

        # Generate code for the call.
        ctx.emit(ir.Call(ret, fn_label, arg_tmp))
        return ret


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

    def code_gen(self, ctx: gen_ctx.CodeGenContext) -> ir.Value:

        # Setup a temporary for the return value of the expression.
        ret = ctx.new_temp(self.type)

        # Generate code for predicate.
        pred_tmp = self.pred.code_gen(ctx)

        # Make two new labels.
        else_lbl = ctx.new_label()
        end_lbl = ctx.new_label()

        # Emit the conditional jump instr.
        ctx.emit(ir.IfFalse(pred_tmp, else_lbl))

        # Generate the yes branch, then add a "goto end".
        yes_ret = self.yes.code_gen(ctx)
        ctx.emit(ir.Store(ret, yes_ret))
        ctx.emit(ir.Goto(end_lbl))

        # Generate the else branch
        ctx.emit(else_lbl)
        no_ret = self.no.code_gen(ctx)
        ctx.emit(ir.Store(ret, no_ret))

        # Specify the end of the if statement
        ctx.emit(end_lbl)

        return ret


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

    def code_gen(self, ctx: gen_ctx.CodeGenContext) -> ir.Value:

        # First generate the right hand side of the binding.
        right_tmp = self.right.code_gen(ctx)
        left_tmp = self.left.code_gen(ctx)
        left_tmp = typing.cast(ir.Ident, left_tmp)  # Cast to `ir.Ident` from `ir.Value`.

        # Emit the binding `left = right`.
        ctx.emit(ir.Store(left_tmp, right_tmp))

        ret = ctx.new_temp(self.type)  # TODO: Optimize this away? Only need one return temporary?

        # Generate code for the body, then save the result in ret.
        body_tmp = self.body.code_gen(ctx)
        ctx.emit(ir.Store(ret, body_tmp))

        return ret
