import functools
from itertools import tee
from typing import Iterator, Callable, TypeVar, Iterable

from fauxcaml.utils import unicode


def fresh_greek_stream() -> Iterator[str]:
    yield from unicode.GREEK_LOWER
    n = 1
    while True:
        yield from (f"{ch}{n}" for ch in unicode.GREEK_LOWER)
        n += 1


def pairwise(seq):
    first, second = tee(iter(seq))
    next(second)
    return zip(first, second)


def set_to_str(s):
    ele_list = ", ".join({str(v) for v in s})
    return f"{{{ele_list}}}"


def instance(cls):
    """
    A class decorator that replaces its input class with an instance of that
    class.
    :param cls:
    :return:
    """
    return cls()


def flip(func):
    """Source: https://www.burgaud.com/foldl-foldr-python"""
    @functools.wraps(func)
    def newfunc(x, y):
        return func(y, x)
    return newfunc


T = TypeVar("T")
U = TypeVar("U")
V = TypeVar("V")


def foldr(func: Callable[[T, U], V], xs: Iterable):
    """Source: https://www.burgaud.com/foldl-foldr-python"""
    return functools.reduce(flip(func), reversed(xs))


def cache_in_attr(attr_name: str):
    """
    A decorator that will cache a method's returned value in the attribute
    specified by `attr_name`. The instance that owns the decorated method
    is where the value will be stored.
    """
    def decorator(fn):
        @functools.wraps(fn)
        def new_fn(self, *args, **kwargs):
            ret = fn(self, *args, **kwargs)
            setattr(self, attr_name, ret)
            return ret
        return new_fn
    return decorator
