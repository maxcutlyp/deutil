from deutil.fol_cm import (
    interpretations,
    total_interpretations,
    find_counter_model,
)
from deutil.expr import (
    SymbolicTerm,
    UnboundPredicate,
    Predicate,
    ExpressionParser,
)

import itertools
from frozendict import frozendict
import logging
import pytest

def test_interpretations_small() -> None:
    preds = [
        UnboundPredicate('F', 1),
    ]
    domain = [
        SymbolicTerm('a'),
        SymbolicTerm('b'),
    ]

    intps = list(interpretations(preds, domain))

    expect = [
        {
            Predicate('F', [SymbolicTerm('a')]): True,
            Predicate('F', [SymbolicTerm('b')]): True,
        },
        {
            Predicate('F', [SymbolicTerm('a')]): True,
            Predicate('F', [SymbolicTerm('b')]): False,
        },
        {
            Predicate('F', [SymbolicTerm('a')]): False,
            Predicate('F', [SymbolicTerm('b')]): True,
        },
        {
            Predicate('F', [SymbolicTerm('a')]): False,
            Predicate('F', [SymbolicTerm('b')]): False,
        },
    ]

    assert len(intps) == len(expect)
    assert set(frozendict(intp) for intp in intps) == set(frozendict(e) for e in expect)

def test_interpretations_medium() -> None:
    preds = [
        UnboundPredicate('F', 3),
        UnboundPredicate('G', 3),
    ]

    domain = [
        SymbolicTerm('a'),
        SymbolicTerm('b'),
    ]

    check_interpretations(preds, domain)

def test_interpretations_large() -> None:
    preds = [
        UnboundPredicate('F', 1),
        UnboundPredicate('G', 2),
        UnboundPredicate('H', 2),
        UnboundPredicate('I', 3),
    ]

    domain = [
        SymbolicTerm('a'),
        SymbolicTerm('b'),
    ]

    check_interpretations(preds, domain)

def test_interpretations_many_small() -> None:
    check_interpretations_many(max_preds=2, max_domain_sz=2, max_arity=2)

@pytest.mark.slow
def test_interpretations_many_large() -> None:
    check_interpretations_many(max_preds=4, max_domain_sz=4, max_arity=4)

def check_interpretations_many(max_preds: int, max_domain_sz: int, max_arity: int) -> None:
    for n_preds, n_domain in itertools.product(range(1, max_preds + 1), range(1, max_domain_sz + 1)):
        domain = [SymbolicTerm(f'x{i}') for i in range(n_domain)]
        for arities in itertools.product(range(1, max_arity + 1), repeat=n_preds):
            preds = [UnboundPredicate(f'P{i}', arity) for i, arity in enumerate(arities)]
            check_interpretations(preds, domain)

def check_interpretations(preds: list[UnboundPredicate], domain: list[SymbolicTerm]) -> None:
    expected_total = total_interpretations(preds, domain)
    logging.debug(f'{preds=} {len(domain)=} {expected_total=}')

    intps = list(interpretations(preds, domain))

    assert len(intps) == len(set(frozendict(intp) for intp in intps))
    assert len(intps) == expected_total

def test_find_counter_model_simple() -> None:
    prems = [
        ExpressionParser('\\Vx(Fx -> Gx)').parse(),
        ExpressionParser('\\VxGx').parse(),
    ]
    conc = ExpressionParser('\\VxFx').parse()

    cm = find_counter_model(prems, conc)
    assert cm is not None

def test_find_counter_model_none() -> None:
    prems = [
        ExpressionParser('\\Vx(Fx -> Gx)').parse(),
        ExpressionParser('\\VxFx').parse(),
    ]
    conc = ExpressionParser('\\VxGx').parse()

    cm = find_counter_model(prems, conc)
    assert cm is None

