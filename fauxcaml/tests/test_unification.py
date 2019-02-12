import pytest

from fauxcaml.semantics.check import Checker
from fauxcaml.semantics.typ import *
from fauxcaml.semantics.unifier_set import UnificationError


def test_concrete_atom_unification():
    checker = Checker()
    checker.unify(Int, Int)


def test_concrete_poly_unification():
    checker = Checker()
    checker.unify(Tuple(Int, Bool), Tuple(Int, Bool))


def test_var_unification():
    checker = Checker()
    T = checker.fresh_var()
    U = checker.fresh_var()

    assert not checker.unifiers.same_set(T, U)

    checker.unify(T, U)
    assert checker.unifiers.same_set(T, U)

    checker.unify(T, Bool)
    assert checker.unifiers.same_set(T, Bool)
    assert checker.unifiers.same_set(U, Bool)


def test_var_more_unification():
    checker = Checker()
    T = checker.fresh_var()
    U = checker.fresh_var()

    checker.unify(Tuple(T, Bool), Tuple(Int, U))
    assert checker.unifiers.same_set(T, Int)
    assert checker.unifiers.same_set(U, Bool)


def test_unification_error():
    checker = Checker()
    T = checker.fresh_var()

    with pytest.raises(UnificationError):
        checker.unify(Tuple(Bool, Int), Tuple(T, T))

    with pytest.raises(UnificationError):
        checker.unify(Tuple(Bool, Int), Tuple(Bool))

    with pytest.raises(UnificationError):
        checker.unify(Tuple(Bool, Int), Fn(Bool, Int))


def test_basic_generic_non_generic_unification():
    checker = Checker()

    generic = checker.fresh_var()
    non_generic = checker.fresh_var(non_generic=True)

    checker.unify(generic, non_generic)

    assert checker.is_non_generic(generic)


def test_basic_generic_non_generic_unification_reversed():
    checker = Checker()

    generic = checker.fresh_var()
    non_generic = checker.fresh_var(non_generic=True)

    checker.unify(non_generic, generic)

    assert checker.is_non_generic(generic)


def test_complex_generic_non_generic_unification():
    checker = Checker()

    generic = checker.fresh_var()
    non_generic = checker.fresh_var(non_generic=True)

    t = Tuple(generic)
    checker.unify(non_generic, t)

    assert checker.is_non_generic(generic)


def test_concretize():
    checker = Checker()

    T = checker.fresh_var()
    U = checker.fresh_var()
    tup = Tuple(T, Fn(U, Int))

    checker.unify(T, List(Bool))
    checker.unify(U, T)

    concrete = checker.concretize(tup)
    assert concrete == Tuple(List(Bool), Fn(List(Bool), Int))

