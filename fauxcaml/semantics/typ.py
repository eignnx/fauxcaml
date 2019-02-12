from fauxcaml.utils import instance
from fauxcaml.utils import unicode


class Type:
    def __eq__(self, other):
        return type(self) is type(other)


class Var(Type):
    """
    Represents a type variable.
    α, β, γ
    """

    def __init__(self, val):
        self.val = val

    def __repr__(self):
        cls_name = self.__class__.__name__
        val = repr(self.val)
        return f"{cls_name}({val})"

    def __str__(self):
        return str(self.val)

    def __hash__(self):
        return hash((self.__class__, self.val))

    def __eq__(self, other):
        return super().__eq__(other) and self.val == other.val


class Poly(Type):
    JOIN = None
    SIZE = None
    PARENS = None

    def __init__(self, *vals):
        if self.SIZE is not None and len(vals) > self.SIZE:
            cls_name = self.__class__.__name__
            msg = f"{cls_name} constructor takes at most {self.SIZE} arguments, {len(vals)} given!"
            raise ValueError(msg)
        self.vals = vals

    def __repr__(self):
        if self.SIZE == 0:
            return self.__class__.__name__
        cls_name = self.__class__.__name__
        vals = ", ".join(repr(v) for v in self.vals)
        return f"{cls_name}({vals})"

    def __str__(self):
        if self.SIZE == 0:
            return self.__class__.__name__
        else:
            sep = f" {self.JOIN} " if self.JOIN is not None else ", "
            vals = sep.join(str(v) for v in self.vals)
            lparen, rparen = self.PARENS if self.PARENS is not None else ("(", ")")
            return f"{lparen}{vals}{rparen}"

    def __hash__(self):
        return hash((self.__class__, self.vals))

    def __eq__(self, other):
        return super().__eq__(other) and \
               len(self.vals) == len(other.vals) and \
               all(x == y for x, y in zip(self.vals, other.vals))

    def __iter__(self):
        """
        Allows unpacking:
            x, y, z = Tuple(1, 2, 3)
        """
        return iter(self.vals)


class Tuple(Poly):
    JOIN = unicode.CROSS


class List(Poly):
    JOIN = None
    SIZE = 1

    def __str__(self):
        [val] = self.vals
        return f"(list {val})"


class Fn(Poly):
    JOIN = unicode.ARROW
    SIZE = 2


@instance
class Int(Poly):
    SIZE = 0


@instance
class Bool(Poly):
    SIZE = 0


@instance
class Unit(Poly):
    SIZE = 0
