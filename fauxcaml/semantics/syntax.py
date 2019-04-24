from __future__ import annotations

import functools
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Dict, Optional, Set, Callable, List, Tuple

from fauxcaml.lir import gen_ctx, lir, intrinsics
from fauxcaml.semantics import check
from fauxcaml.semantics import typ
from fauxcaml.semantics import unifier_set


class AstNode(ABC):
    def __init__(self):
        self._type: Optional[typ.Type] = None
        self._unifiers: Optional[unifier_set.UnifierSet] = None

    @abstractmethod
    def infer_type(self, checker: check.Checker) -> typ.Type:
        pass

    @abstractmethod
    def to_lir(self, ctx: gen_ctx.NasmGenCtx) -> lir.Value:
        raise NotImplementedError

    @abstractmethod
    def captures(self) -> Set[Ident]:
        """
        Returns a set of all captured variables ie those variables that are used
        in the current `AstNode` (`self`), but not defined in the current
        `AstNode`. See http://matt.might.net/articles/closure-conversion/
        for discussion and example implementation in Racket.
        """
        pass

    @staticmethod
    def cache_type(fn: Callable[[AstNode, check.Checker], typ.Type]):
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


@dataclass
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
        if self.name in ctx.local_names:
            return ctx.local_names[self.name]
        else:
            tmp = ctx.new_temp64()
            ctx.add_instr(
                lir.EnvLookup(
                    index=ctx.captured_names[self.name],
                    res=tmp,
                    name=self.name
                )
            )
            return tmp

    def captures(self) -> Set[Ident]:
        return {self}

    def __str__(self):
        return self.name

    def __hash__(self):
        return hash(self.name)


@dataclass
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

    def captures(self) -> Set[Ident]:
        return set()

    def __str__(self):
        return str(self.value)


@dataclass
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

    def to_lir(self, ctx: gen_ctx.NasmGenCtx) -> lir.Value:
        capture_list = list(self.captures())
        capture_values = [ident.to_lir(ctx) for ident in capture_list]

        # These `int` values are indices and will be used by `EnvLookup` instructions.
        capture_indices: Dict[str, int] = {ident.name: index for index, ident in enumerate(capture_list)}

        lambda_name = f"lambda${id(self):X}"  # TODO: Is this safe?
        with ctx.new_fn_def(lambda_name, capture_indices) as (lbl, param_tmp):
            param_name = self.param.name
            ctx.local_names[param_name] = param_tmp
            ret = self.body.to_lir(ctx)
            ctx.add_instr(lir.Return(ret))

        closure_tmp = ctx.new_temp64()

        ctx.add_instr(
            lir.CreateClosure(
                fn_lbl=lbl,
                captures=capture_values,
                ret=closure_tmp,
                recursive=False,  # ASSERTION: No lambda in this context is recursive.
            )
        )

        return closure_tmp

    def captures(self) -> Set[Ident]:
        return self.body.captures() - {self.param}


@dataclass
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
        ret = ctx.new_temp64() if self.type != typ.Unit else lir.Temp0()
        arg_tmp = self.arg.to_lir(ctx)
        fn_tmp = self.fn.to_lir(ctx)
        if not isinstance(fn_tmp, lir.Temp64):
            msg = f"Cannot call something other than a 64-bit temporary as if it " \
                  f"were a closure! Given type '{type(fn_tmp)}'"
            raise ValueError(msg)
        instr = lir.CallClosure(fn_tmp, arg_tmp, ret)
        ctx.add_instr(instr)
        return ret

    def captures(self) -> Set[Ident]:
        return self.fn.captures() | self.arg.captures()


@dataclass
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

    def to_lir(self, ctx: gen_ctx.NasmGenCtx) -> lir.Value:
        # Setup a temporary for the return value of the expression.
        ret = ctx.new_temp64()

        # Generate code for predicate.
        pred_tmp = self.pred.to_lir(ctx)

        # Make two new labels.
        else_lbl = ctx.new_label()
        end_lbl = ctx.new_label()

        # Emit the conditional jump instr.
        ctx.add_instr(lir.IfFalse(pred_tmp, else_lbl))

        # Generate the yes branch, then add a "goto end".
        yes_ret = self.yes.to_lir(ctx)
        ctx.add_instrs([
            lir.Assign(ret, yes_ret),
            lir.Goto(end_lbl),
        ])

        ctx.add_instr(else_lbl.as_instr())

        # Generate the else branch
        no_ret = self.no.to_lir(ctx)
        ctx.add_instr(lir.Assign(ret, no_ret))

        # Specify the end of the if statement
        ctx.add_instr(end_lbl.as_instr())

        return ret

    def captures(self) -> Set[Ident]:
        return self.pred.captures() | self.yes.captures() | self.no.captures()


@dataclass
class Let(AstNode):
    """
    let left = right in body
    """
    left: Ident
    right: AstNode
    body: AstNode
    recursive: bool = False

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

    def to_lir(self, ctx: gen_ctx.NasmGenCtx) -> lir.Value:
        if isinstance(self.right, Lambda):

            with ctx.new_fn_def(self.left.name) as (lbl, param_tmp):
                param_name = self.right.param.name
                ctx.local_names[param_name] = param_tmp
                ret = self.right.body.to_lir(ctx)
                ctx.add_instr(lir.Return(ret))

            left_tmp = ctx.new_temp64()
            ctx.local_names[self.left.name] = left_tmp

            ctx.add_instr(
                lir.CreateClosure(
                    fn_lbl=lbl,
                    captures=[],
                    ret=left_tmp,
                    recursive=self.recursive,
                )
            )
        else:
            tmp = self.right.to_lir(ctx)
            ctx.local_names[self.left.name] = tmp

        return self.body.to_lir(ctx)

    def captures(self) -> Set[Ident]:
        return (self.body.captures() | self.right.captures()) - {self.left}


@dataclass
class TupleLit(AstNode):
    vals: Tuple[AstNode, ...]

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

    def captures(self) -> Set[Ident]:
        return {  # The poor-lang's flatmap.
            capture
            for val in self.vals
            for capture in val.captures()
        }


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
    recursive: bool = False

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

            # NOTE: This list specifically does NOT include the recursively defined identifier (if the `let` is
            # recursive). For instance, if this LetStmt was like `let rec f x = ... f ... ;;`, the ident `f` would
            # NOT be included here. This is because `CreateClosure` must assign recursive bindings internally,
            # and not based on the list of captured values.
            capture_list = list(self.captures())
            capture_values = [ident.to_lir(ctx) for ident in capture_list]

            # HOWEVER: The recursively bound identifier will be included AT THE FRONT of the capture list when
            # constructing a `Dict[str, int]` so that code can be generated for `self.body`. These `int` values are
            # indices and will be used by `EnvLookup` instructions.
            capture_list_with_rec = ([self.left] if self.recursive else []) + capture_list
            capture_indices: Dict[str, int] = {ident.name: index for index, ident in enumerate(capture_list_with_rec)}

            with ctx.new_fn_def(self.left.name, capture_indices) as (lbl, param_tmp):
                param_name = self.right.param.name
                ctx.local_names[param_name] = param_tmp
                ret = self.right.body.to_lir(ctx)
                ctx.add_instr(lir.Return(ret))

            left_tmp = ctx.new_temp64()
            ctx.local_names[self.left.name] = left_tmp

            ctx.add_instr(
                lir.CreateClosure(
                    fn_lbl=lbl,
                    captures=capture_values,
                    ret=left_tmp,
                    recursive=self.recursive
                )
            )
        else:
            val = self.right.to_lir(ctx)
            ctx.local_names[self.left.name] = val

        return lir.Temp0()

    def captures(self) -> Set[Ident]:
        return self.right.captures() - {self.left}


@dataclass
class TopLevelStmts(AstNode):
    stmts: List[AstNode]

    @AstNode.cache_type
    def infer_type(self, checker: check.Checker) -> typ.Type:
        for stmt in self.stmts:
            stmt.infer_type(checker)
        return typ.Unit

    def to_lir(self, ctx: gen_ctx.NasmGenCtx) -> lir.Temp:
        for stmt in self.stmts:
            stmt.to_lir(ctx)
        return lir.Temp0()

    def captures(self) -> Set[Ident]:
        return {  # The poor-lang's flatmap.
            capture
            for stmt in self.stmts
            for capture in stmt.captures()
        }

    def __add__(self, other):
        return TopLevelStmts(self.stmts + other.stmts)

