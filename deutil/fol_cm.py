# Find counter model

# 1. Find all definite names in prems + conc
# 2. Find all predicates and their arities
# 3. Find all quantifiers
# 4. Init domain = all such definite names
#   5. Assign truth values to predicates applied to definite names (binary logic)
#   6. Evaluate expressions with these assignments (treat preds with defined arguments as propositions)
#   7. If prems evaluate to true and conc evaluates to false: return countermodel
#   8. Else: Go to next assignment (5)
# 9. If still no counter model, add a new definite name to the domain
# 10. If len(new definite names) <= len(quantifiers), goto 5 (try again)
# 11. Else, conclude no countermodel exists

# Note: this is not perfect, and will not work if the countermodel requires an infinte domain.

import typing as t
import itertools

from .expr import (
    Expr,
    FOLInterpretation,
    UniversalQuantifier, ExistentialQuantifier,
    SymbolicTerm,
    Predicate,
    UnboundPredicate,
)

from .termutils import (
    underline,
)

def total_interpretations(preds: t.Iterable[UnboundPredicate], domain: t.Collection[SymbolicTerm]) -> int:
    pred_arities = dict[int, set[UnboundPredicate]]()
    for pred in preds:
        pred_arities.setdefault(pred.arity, set()).add(pred)

    expected_total = 1
    for arity, preds_ in pred_arities.items():
        num_preds = len(preds_)
        num_assignments_per_pred = len(domain) ** arity
        expected_total *= 2 ** (num_preds * num_assignments_per_pred)

    return expected_total

def wrap_progress_iter[T](iterable: t.Iterable[T], total: int, epoch: int = 1741) -> t.Iterable[T]:
    def p() -> None:
        print(f'\r{i} / {total} [{i/total:.2%}]', end='')

    i = 0
    try:
        for item in iterable:
            yield item
            i += 1
            if i % epoch == 0:
                p()

        if i > epoch:
            p()
    finally:
        if i > epoch:
            print()

def wrap_progress_func[R](func: t.Callable[[t.Callable[[], None]], R], total: int, epoch: int = 1741) -> R:
    def p() -> None:
        print(f'\r{i} / {total} [{i/total:.2%}]', end='')

    i = 0
    def progress() -> None:
        nonlocal i
        i += 1
        if i % epoch == 0:
            p()

    try:
        res = func(progress)
        if i > epoch:
            p()
        return res
    finally:
        if i > epoch:
            print()

def interpretations(preds: t.Collection[UnboundPredicate], domain: t.Collection[SymbolicTerm], show_progress: bool = True) -> t.Iterable[FOLInterpretation]:
    preds = list(preds)
    domain = list(domain)

    if show_progress:
        yield from wrap_progress_iter(
            _interpretations(preds, domain),
            total = total_interpretations(preds, domain),
        )
    else:
        yield from _interpretations(preds, domain)

def _interpretations(preds: list[UnboundPredicate], domain: list[SymbolicTerm]) -> t.Iterable[FOLInterpretation]:
    if len(preds) == 0:
        yield {}
        return

    pred = preds[0]
    for assignment in itertools.product([True, False], repeat=len(domain) ** pred.arity):
        intp: FOLInterpretation = { pred.bind(args): value for args, value in zip(itertools.product(domain, repeat=pred.arity), assignment) }
        for rest in _interpretations(preds[1:], domain):
            yield dict(intp) | dict(rest)

def find_counter_model(prems: list[Expr], conc: Expr, show_progress: bool = True) -> FOLInterpretation | None:
    quantifiers = set.union(
        *(prem.extract(UniversalQuantifier) | prem.extract(ExistentialQuantifier) for prem in prems),
        conc.extract(UniversalQuantifier) | conc.extract(ExistentialQuantifier),
    )
    bound_names = { q.variable for q in quantifiers }

    all_names = set.union(
        *(prem.extract(SymbolicTerm) for prem in prems),
        conc.extract(SymbolicTerm),
    )

    preds = {
        UnboundPredicate.from_predicate(pred)
        for pred in set.union(
            *(prem.extract(Predicate) for prem in prems),
            conc.extract(Predicate),
        )
    }

    # Assume all unbound names are constants (definite names)
    # TODO: This does not work if a name used as a quantifier variable is also used as a constant
    # elsewhere (e.g. in another premise). This is an error state, but it's non-trivial to detect.
    # For now we just leave it until it causes a problem when we try to evaluate the expression
    # containing the problematic predicate.
    bound_names = all_names - bound_names
    domain = { *bound_names }

    if not domain:
        # FOL assumes domains are non-empty
        domain.add(SymbolicTerm('x0'))

    def _impl(progress: t.Callable[[], None]) -> FOLInterpretation | None:
        while len(domain - bound_names) <= len(quantifiers):
            for intp in interpretations(preds, domain, show_progress=False):
                if all(prem.evaluate(intp) for prem in prems) and not conc.evaluate(intp):
                    return intp
                progress()
            domain.add(SymbolicTerm(f'x{len(domain) - len(bound_names)}'))
        return None

    if show_progress:
        # Calculate total number of interpretations to show progress by simulating the above loop
        total = 0
        _domain = set(domain)
        while len(_domain - bound_names) <= len(quantifiers):
            total += total_interpretations(preds, _domain)
            _domain.add(SymbolicTerm(f'x{len(_domain) - len(bound_names)}'))

        return wrap_progress_func(_impl, total=total)
    else:
        return _impl(lambda: None)

def find_cm(prems: list[Expr], conc: Expr) -> None:
    print('Searching for a countermodel...')

    intp = find_counter_model(prems, conc)
    if intp is None:
        print('No countermodel found. This does not necessarily mean that one does not exist.')
        return

    print('Countermodel found:')
    for pred, value in intp.items():
        print(f'  {pred}: {value}')
    print()

