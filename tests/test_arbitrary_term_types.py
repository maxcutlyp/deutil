import pytest

from deutil.expr import (
    SymbolicTerm,
    ArbitraryTerm,
)

def test_explicit_arbitrary_term() -> None:
    a = ArbitraryTerm("a'")
    assert isinstance(a, ArbitraryTerm)

def test_implicit_arbitrary_term() -> None:
    a = SymbolicTerm("a'")
    assert isinstance(a, ArbitraryTerm)

def test_non_arbitrary_term() -> None:
    a = SymbolicTerm("a")
    assert not isinstance(a, ArbitraryTerm)

def test_bad_arbitrary_term() -> None:
    with pytest.raises(ValueError):
        ArbitraryTerm("a")

