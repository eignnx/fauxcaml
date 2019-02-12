from typing import Set

from fauxcaml.semantics import typ
from fauxcaml import utils
from fauxcaml.semantics.disjoint_set import DisjointSet


class UnificationError(Exception):
    def __init__(self, msg):
        self.msg = msg


class RecursiveUnificationError(UnificationError):
    pass


class UnifierSet(DisjointSet):
    def __init__(self):
        super().__init__()
        self._fresh_var_names = utils.fresh_greek_stream()
        self.non_generic_vars: Set[typ.Var] = set()

    def fresh_var(self, non_generic=False) -> typ.Var:
        """
        A Var should always be added to the global UnifierSet whenever it's
        created. Returns a non-generic type variable unless otherwise specified.
        """
        v = typ.Var(next(self._fresh_var_names))
        self.add(v)
        if non_generic:
            self.non_generic_vars.add(v)
        return v

    def occurs_in_type(self, t1, t2):
        if t1 == t2:
            return True
        elif isinstance(t2, typ.Poly):
            return any(self.occurs_in_type(t1, t) for t in t2.vals)
        else:
            return False

    def unify(self, t1: typ.Type, t2: typ.Type):

        if type(t1) is typ.Var:

            # Ensure they're both in the DisjointSet.
            self.add(t1)
            self.add(t2)

            # "In unifying a non-generic type variable to a term, all the type
            # variables contained in that term become non-generic."
            #   -- Luca Cardelli, Basic Polymorphic Typechecking, 1988, pg. 11

            if self.is_non_generic(t1):
                self.make_non_generic(t2)

            if type(t2) is typ.Var and self.is_non_generic(t2):
                self.make_non_generic(t1)

            if t1 == t2:
                return  # Type variables are identical, no need to unify.
            elif self.occurs_in_type(t1, t2):
                raise RecursiveUnificationError
            else:
                self.join(t1, t2)

        elif isinstance(t1, typ.Poly) and isinstance(t2, typ.Poly):
            if type(t1) is not type(t2):
                msg = f"Type mismatch: {t1} != {t2}"
                raise UnificationError(msg)
            elif len(t1.vals) != len(t2.vals):
                msg = f"Type mismatch: {t1} has different arity than {t2}!"
                raise UnificationError(msg)
            else:
                for x, y in zip(t1.vals, t2.vals):
                    self.unify(x, y)

        elif isinstance(t1, typ.Poly) and type(t2) is typ.Var:
            return self.unify(t2, t1)  # Swap args and call again

    def join_roots(self, r1, r2):
        size1, size2 = self.map[r1], self.map[r2]

        if type(r1) is typ.Var and type(r2) is not typ.Var:
            # `r2` is something concrete, make it the root.
            self.map[r2] += size1
            self.map[r1] = r2
        elif type(r2) is typ.Var and type(r1) is not typ.Var:
            # `r1` is something concrete, make it the root.
            self.map[r1] += size2
            self.map[r2] = r1
        elif type(r1) is typ.Var and type(r2) is typ.Var:
            # Use weighting heuristic to keep it fast.
            if size1 > size2:
                self.map[r1] += size2
                self.map[r2] = r1
            else:
                self.map[r2] += size1
                self.map[r1] = r2
        else:
            if type(r1) is not type(r2):
                msg = f"Type mismatch: {r1} != {r2}"
                raise UnificationError(msg)
            else:
                self.unify(r1, r2)

    def make_non_generic(self, t: typ.Type) -> None:
        """
        Recursively searches for `Var`s in `t`, making them all non-generic.
        """
        if type(t) is typ.Var:
            self.non_generic_vars.add(t)
        elif isinstance(t, typ.Poly):
            for x in t.vals:
                self.make_non_generic(x)

    def is_non_generic(self, v):
        return v in self.non_generic_vars

    def concretize(self, t: typ.Type) -> typ.Type:
        """
        Recursively builds up a type by replacing all known `Var`s with the
        concrete types they refer to.

        Ex:
            If T has been unified with Int:
                self.concretize(T) -> Int
                self.concretize(Tuple(T)) -> Tuple(Int)
        """
        if type(t) is typ.Var:
            r = self.root_of(t)
            return r if r == t else self.concretize(r)
        elif isinstance(t, typ.Poly):
            cls = type(t)
            vals = (self.concretize(v) for v in t.vals)
            return cls(*vals)

    def make_generic(self, v: typ.Var):
        self.non_generic_vars.remove(v)


