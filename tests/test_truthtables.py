from deutil.expr import (
    And,
    Or,
    Not,
    Imp,
    Bij,
    Atom,
    ExpressionParser,
)

from deutil.truthtables import (
    make_truth_table,
    render_truth_table,
    TruthTable,
)

from itertools import product
from frozendict import frozendict
import typing as t

P = Atom('P')
Q = Atom('Q')
R = Atom('R')
S = Atom('S')

def test_ttbf_1() -> None:
    expr = Imp(Imp(Imp(R, S), R), R)

    # Test all combinations of truth values for R and S
    for R_val, S_val in product([True, False], repeat=2):
        assignments = {R: R_val, S: S_val}
        assert expr.evaluate(assignments) == True

def test_and() -> None:
    A = Atom('A')
    B = Atom('B')
    expr = And(A, B)

    assert expr.evaluate({A: True, B: True}) == True
    assert expr.evaluate({A: True, B: False}) == False
    assert expr.evaluate({A: False, B: True}) == False
    assert expr.evaluate({A: False, B: False}) == False

def test_or() -> None:
    A = Atom('A')
    B = Atom('B')
    expr = Or(A, B)

    assert expr.evaluate({A: True, B: True}) == True
    assert expr.evaluate({A: True, B: False}) == True
    assert expr.evaluate({A: False, B: True}) == True
    assert expr.evaluate({A: False, B: False}) == False

def test_not() -> None:
    A = Atom('A')
    expr = Not(A)

    assert expr.evaluate({A: True}) == False
    assert expr.evaluate({A: False}) == True

def test_imp() -> None:
    A = Atom('A')
    B = Atom('B')
    expr = Imp(A, B)

    assert expr.evaluate({A: True, B: True}) == True
    assert expr.evaluate({A: True, B: False}) == False
    assert expr.evaluate({A: False, B: True}) == True
    assert expr.evaluate({A: False, B: False}) == True

def test_complex_expr() -> None:
    A = Atom('A')
    B = Atom('B')
    C = Atom('C')
    expr = Or(And(A, B), Not(C))

    assert expr.evaluate({A: True, B: True, C: True}) == True
    assert expr.evaluate({A: True, B: False, C: True}) == False
    assert expr.evaluate({A: False, B: True, C: True}) == False
    assert expr.evaluate({A: False, B: False, C: True}) == False
    assert expr.evaluate({A: True, B: True, C: False}) == True
    assert expr.evaluate({A: True, B: False, C: False}) == True
    assert expr.evaluate({A: False, B: True, C: False}) == True
    assert expr.evaluate({A: False, B: False, C: False}) == True

def test_parser_1() -> None:
    expr_str = '(((R -> S) -> R) -> R)'
    parser = ExpressionParser(expr_str)
    expr = parser.parse()
    assert expr == Imp(Imp(Imp(Atom('R'), Atom('S')), Atom('R')), Atom('R'))

def test_parser_renderer() -> None:
    expr = Imp(Imp(Imp(R, S), R), R)
    rendered = expr.render()
    expr_new = ExpressionParser(rendered).parse()
    assert expr == expr_new

def test_render_tt() -> None:
    expr = Imp(Imp(Imp(R, S), R), R)
    truth_table = make_truth_table(expr)
    rendered = render_truth_table(truth_table)
    expected = """\
\033[4m R | S | (((R → S) → R) → R) |\033[24m
 T | T |          T          |
 T | F |          T          |
 F | T |          T          |
 F | F |          T          |\
""".replace('|', '│')
    assert rendered == expected

def test_render_tt_many() -> None:
    for _ in range(100):
        test_render_tt()

def test_tt_multiple() -> None:
    p1 = Or(P, Q)
    p2 = Or(R, S)
    conc = Or(And(P, R), And(Q, S))
    tt = make_truth_table(p1, p2, conc)

    T = True
    F = False
    expected = [
        ({ P: T, Q: T, R: T, S: T}, ((p1, T), (p2, T), (conc, T))),
        ({ P: T, Q: T, R: T, S: F}, ((p1, T), (p2, T), (conc, T))),
        ({ P: T, Q: T, R: F, S: T}, ((p1, T), (p2, T), (conc, T))),
        ({ P: T, Q: T, R: F, S: F}, ((p1, T), (p2, F), (conc, F))),
        ({ P: T, Q: F, R: T, S: T}, ((p1, T), (p2, T), (conc, T))),
        ({ P: T, Q: F, R: T, S: F}, ((p1, T), (p2, T), (conc, T))),
        ({ P: T, Q: F, R: F, S: T}, ((p1, T), (p2, T), (conc, F))),
        ({ P: T, Q: F, R: F, S: F}, ((p1, T), (p2, F), (conc, F))),
        ({ P: F, Q: T, R: T, S: T}, ((p1, T), (p2, T), (conc, T))),
        ({ P: F, Q: T, R: T, S: F}, ((p1, T), (p2, T), (conc, F))),
        ({ P: F, Q: T, R: F, S: T}, ((p1, T), (p2, T), (conc, T))),
        ({ P: F, Q: T, R: F, S: F}, ((p1, T), (p2, F), (conc, F))),
        ({ P: F, Q: F, R: T, S: T}, ((p1, F), (p2, T), (conc, F))),
        ({ P: F, Q: F, R: T, S: F}, ((p1, F), (p2, T), (conc, F))),
        ({ P: F, Q: F, R: F, S: T}, ((p1, F), (p2, T), (conc, F))),
        ({ P: F, Q: F, R: F, S: F}, ((p1, F), (p2, F), (conc, F))),
    ]

    expected_tt: TruthTable = {
        frozendict(assignments) : t.OrderedDict(results)
        for assignments, results in expected
    }

    assert tt == expected_tt


