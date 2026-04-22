from __future__ import annotations
from abc import ABC, abstractmethod
import typing as t
import re

from .expr import (
    Expr,
    ExpressionParser,
    Atom,
    UnaryOperator,
    BinaryOperator,
    Imp,
    Not,
)

class ProofError(Exception):
    pass

def unify(expr1: Expr, expr2: Expr, bindings: dict[Atom, Expr] | None = None) -> dict[Atom, Expr] | None:
    if bindings is None:
        bindings = {}

    if isinstance(expr1, Atom):
        if expr1 in bindings:
            if bindings[expr1] == expr2:
                return bindings
            return None
        else:
            bindings[expr1] = expr2
            return bindings

    elif type(expr1) != type(expr2):
        return None

    elif isinstance(expr1, UnaryOperator):
        if not isinstance(expr2, UnaryOperator):
            return None
        return unify(expr1.operand, expr2.operand, bindings)

    elif isinstance(expr1, BinaryOperator):
        if not isinstance(expr2, BinaryOperator):
            return None
        bindings_left = unify(expr1.left, expr2.left, bindings)
        if bindings_left is None:
            return None
        return unify(expr1.right, expr2.right, bindings_left)

    else:
        raise ValueError(f'Unknown expression type: {type(expr1)}')

class Rule(ABC):
    prem_lines: tuple[int, ...]
    def __init__(self, prem_lines: tuple[int, ...]):
        self.prem_lines = prem_lines

    @abstractmethod
    def check(self, conc: Expr, prems: list[Expr]) -> None:
        raise NotImplementedError

    @classmethod
    @abstractmethod
    def match(cls, justification: str) -> t.Self | None:
        ''' subclasses may assume that justification is stripped and lowercased '''
        raise NotImplementedError

class SimpleRule(Rule):
    RULES: tuple[tuple[tuple[str, ...], str], ...]

    def __init__(self, prem_lines: tuple[int, ...] = ()):
        self.prem_lines = prem_lines

    def _check_rule(self, rule_prems: list[Expr], rule_conc: Expr, prems: list[Expr], conc: Expr) -> None:
        if len(prems) != len(rule_prems):
            raise ProofError(f'Expected {len(rule_prems)} premises for {self.__class__.__name__} (got {len(prems)})')

        bindings: dict[Atom, Expr] = {}
        for rule_expr, expr in zip(rule_prems + [rule_conc], prems + [conc]):
            new_bindings = unify(rule_expr, expr, bindings)
            if new_bindings is None:
                raise ProofError(f'Expression {expr.render()} does not match expected pattern {rule_expr.render()} for rule {self.__class__.__name__} (got bindings: {bindings})')
            bindings = new_bindings

    def check(self, conc: Expr, prems: list[Expr]) -> None:
        errs = list[ProofError]()
        for rule in self.RULES:
            rule_prems_str, rule_conc_str = rule
            try:
                rule_prems = [ExpressionParser(p).parse() for p in rule_prems_str]
                rule_conc = ExpressionParser(rule_conc_str).parse()
            except Exception as e:
                raise ProofError(f'Error parsing rule {self.__class__.__name__}: {e}')

            try:
                self._check_rule(rule_prems, rule_conc, prems, conc)
            except ProofError as e:
                errs.append(e)
            else:
                return

        if errs:
            raise ProofError(f'No matching rule found for {self.__class__.__name__} with conclusion {conc.render()} and premises {[p.render() for p in prems]} (errors: {errs})')

class Final(Rule):
    def __init_subclass__(cls, **kwargs: t.Any) -> None:
        super().__init_subclass__(**kwargs)
        RULES.add(cls)
RULES = set[type[Rule]]()

def find_rule(justification: str) -> Rule | None:
    justification = justification.strip().lower()
    matched = list[Rule]()
    for rule in RULES:
        if r := rule.match(justification):
            matched.append(r)
    if len(matched) > 1:
        raise ProofError(f'Multiple rules match justification: {justification!r} (matched: {[rule.__class__.__name__ for rule in matched]})')
    elif len(matched) < 1:
        return None

    return matched[0]

class RegexRule(SimpleRule):
    NAMES: tuple[str, ...]

    @classmethod
    def match(cls, justification: str) -> t.Self | None:
        names_pattern = '|'.join(re.escape(name) for name in cls.NAMES)
        lines_pattern = '|'.join(r',\s*'.join(r'\d+' for _ in prems) for prems,_conc in cls.RULES)
        pattern = re.compile(rf'^(?:{names_pattern})\.?:?\s*({lines_pattern})$')
        if m := pattern.match(justification):
            try:
                nums = m.group(1)
                prem_nums = tuple(int(num.strip()) for num in nums.split(','))
            except ValueError:
                raise ProofError(f'Invalid line number in justification: {justification!r}')
            return cls(prem_nums)
        return None

class SubproofRule(Rule):
    NAMES: tuple[str, ...]

    @classmethod
    def match(cls, justification: str) -> t.Self | None:
        names_pattern = '|'.join(re.escape(name) for name in cls.NAMES)
        pattern = re.compile(rf'^(?:{names_pattern})\.?:?\s*(\d+)-(\d+)$')
        if m := pattern.match(justification):
            try:
                start, end = int(m.group(1)), int(m.group(2))
            except ValueError:
                return None
            return cls(tuple(range(start, end + 1)))
        return None

class Premise(SimpleRule, Final):
    RULES = ()

    @classmethod
    def match(cls, justification: str) -> t.Self | None:
        if justification == 'premise' or ('premise'.startswith(justification) and justification.endswith('.')):
            return cls(())
        return None

class Assumption(SimpleRule, ABC):
    RULES = ()

    for_short: str
    for_long: str

    @classmethod
    def match(cls, justification: str) -> t.Self | None:
        try:
            first_word, rest = justification.split(maxsplit=1)
        except ValueError:
            if justification in (f'a{cls.for_short.replace('.', '')}', f'a.{cls.for_short}'):
                return cls(())
            return None

        if not first_word:
            return None

        if first_word == 'assumption' or ('assumption'.startswith(first_word) and first_word.endswith('.')):
            if rest.replace('for ', '') in (cls.for_short.replace('.', ''), cls.for_short, cls.for_long):
                return cls(())
        return None

class AssumptionForCD(Assumption, Final):
    for_short = 'c.d.'
    for_long = 'conditional derivation'

class AssumptionForID(Assumption, Final):
    for_short = 'i.d.'
    for_long = 'indirect derivation'

class ModusPonens(RegexRule, Final):
    RULES = (
        (
            ('(A -> B)', 'A'),
            'B',
        ),
    )
    NAMES = ('mp', 'm.p.', 'modus ponens')

class ModusTollens(RegexRule, Final):
    RULES = (
        (
            ('(A -> B)', '~B'),
            '~A',
        ),
    )
    NAMES = ('mt', 'm.t.', 'modus tollens')

class DoubleNegation(RegexRule, Final):
    RULES = (
        (
            ('~~A',),
            'A',
        ),
        (
            ('A',),
            '~~A',
        ),
    )
    NAMES = ('dn', 'd.n.', 'double negation')

class Repeat(RegexRule, Final):
    RULES = (
        (
            ('A',),
            'A',
        ),
    )
    NAMES = ('repeat',)

class Addition(RegexRule, Final):
    RULES = (
        (
            ('A',),
            '(A v B)',
        ),
        (
            ('A',),
            '(B v A)',
        ),
    )
    NAMES = ('add', 'addition')

class DisjunctiveSyllogism(RegexRule, Final):
    RULES = (
        (
            ('(A v B)', '~A'),
            'B',
        ),
        (
            ('(A v B)', '~B'),
            'A',
        ),
    )
    NAMES = ('ds', 'd.s.', 'disjunctive syllogism')

class Adjunction(RegexRule, Final):
    RULES = (
        (
            ('A', 'B'),
            '(A ^ B)',
        ),
    )
    NAMES = ('adj', 'adjunction')

class Simplification(RegexRule, Final):
    RULES = (
        (
            ('(A ^ B)',),
            'A',
        ),
        (
            ('(A ^ B)',),
            'B',
        ),
    )
    NAMES = ('simp', 'simplification')

class Bicondition(RegexRule, Final):
    RULES = (
        (
            ('(A -> B)', '(B -> A)'),
            '(A <-> B)',
        ),
    )
    NAMES = ('bic', 'bicondition')

class Equivalence(RegexRule, Final):
    RULES = (
        (
            ('(A <-> B)', 'A'),
            'B'
        ),
        (
            ('(A <-> B)', 'B'),
            'A'
        ),
        (
            ('(A <-> B)', '~A'),
            '~B'
        ),
        (
            ('(A <-> B)', '~B'),
            '~A'
        ),
    )
    NAMES = ('equiv', 'equivalence')

THEOREMS = [
    '(A v ~A)',
    '(~(A -> B) <-> (A^~B))',
    '(~(A v B) <-> (~A ^ ~B))',
    '((~A v ~B) <-> ~(A ^ B))',
    '(~(A <-> B) <-> (A <-> ~B))',
    '(~A -> (A -> B))',
    '(A -> (B -> A))',
    '((A -> (B -> R)) -> ((A -> B) -> (A -> R)))',
    '((~A -> ~B) -> ((~A -> B) ->A))',
    '((A -> B) -> (~B -> ~A))',
]
class Theorem(SimpleRule, Final):
    RULES = tuple(
        (
            (),
            theorem,
        )
        for theorem in THEOREMS
    )

    theorem_number: int | None
    def __init__(self, *args: t.Any, theorem_number: int | None, **kwargs: t.Any):
        super().__init__(*args, **kwargs)
        self.theorem_number = theorem_number

    def check(self, conc: Expr, prems: list[Expr]) -> None:
        if self.theorem_number is not None:
            self.RULES = (
                (
                    (),
                    THEOREMS[self.theorem_number - 1],
                ),
            )

        super().check(conc, prems)

    @classmethod
    def match(cls, justification: str) -> t.Self | None:
        first_word = justification.split(maxsplit=1)[0].strip(':.,')
        if first_word == 'theorem' or ('theorem'.startswith(first_word) and first_word.endswith('.')):
            if m := re.search(r'T(\d+)$', justification):
                try:
                    theorem_number = int(m.group(1))
                except ValueError:
                    raise ProofError(f'Invalid theorem number in justification: {justification!r}')
                return cls((), theorem_number=theorem_number)
            return cls((), theorem_number=None)
        return None

class ConditionalDerivation(SubproofRule, Final):
    NAMES = ('cd', 'c.d.', 'conditional derivation')

    def check(self, conc: Expr, prems: list[Expr]) -> None:
        if not isinstance(conc, Imp):
            raise ProofError(f'Conclusion of conditional derivation must be an implication (got {conc.render()})')

        assumption, *_, consequent = prems
        if assumption != conc.left:
            raise ProofError(f'First premise of conditional derivation must match antecedent of conclusion (got {assumption.render()} and {conc.left.render()})')

        if consequent != conc.right:
            raise ProofError(f'Last premise of conditional derivation must match consequent of conclusion (got {consequent.render()} and {conc.right.render()})')

class IndirectDerivation(SubproofRule, Final):
    NAMES = ('id', 'i.d.', 'indirect derivation')

    def check(self, conc: Expr, prems: list[Expr]) -> None:
        try:
            assumption, *_, contradiction_prem, contradiction_negation = prems
        except ValueError:
            raise ProofError(f'Indirect derivation must have at least 3 statements including the assumption (got {[p.render() for p in prems]})')

        if not isinstance(contradiction_negation, Not):
            raise ProofError(f'Last premise of indirect derivation must be a negation (got {contradiction_negation.render()})')

        if contradiction_prem != contradiction_negation.operand:
            raise ProofError(f'Last premise of indirect derivation must be the negation of the second-last premise (got {contradiction_prem.render()} and {contradiction_negation.operand.render()})')

        if not isinstance(assumption, Not):
            raise ProofError(f'First premise of indirect derivation must be a negation (got {assumption.render()})')

        if assumption.operand != conc:
            raise ProofError(f'First premise of indirect derivation must be the negation of the conclusion (got {assumption.operand.render()} and {conc.render()})')

