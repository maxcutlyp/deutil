from __future__ import annotations
from abc import ABC, abstractmethod
import typing as t
import re

from .expr import (
    Expr,
    ExpressionParser,
    Atom,
    Imp,
    Not,
    unify,
    extract_symbolic_terms,
    replace_symbolic_term,
    ExistentialQuantifier,
    UniversalQuantifier,
)
if t.TYPE_CHECKING:
    from .proof import Proof

class ProofError(Exception):
    pass

class InferenceRule(ABC):
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

    @classmethod
    @abstractmethod
    def help(cls) -> str:
        raise NotImplementedError

class SubproofRule(ABC):
    NAMES: tuple[str, ...]

    start: int
    end: int
    def __init__(self, start: int, end: int):
        self.start = start
        self.end = end

    @abstractmethod
    def check(self, conc: Expr, subproof: Proof) -> None:
        raise NotImplementedError

    @classmethod
    def match(cls, justification: str) -> t.Self | None:
        names_pattern = '|'.join(re.escape(name.lower()) for name in cls.NAMES)
        pattern = re.compile(rf'^(?:{names_pattern})\.?:?\s*(\d+)-(\d+)$')
        if m := pattern.match(justification):
            try:
                start, end = int(m.group(1)), int(m.group(2))
            except ValueError:
                return None
            return cls(start, end)
        return None

    @classmethod
    @abstractmethod
    def help(cls) -> str:
        raise NotImplementedError

class SimpleRule(InferenceRule):
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

type Rule = InferenceRule | SubproofRule
class Final:
    def __init_subclass__(cls, **kwargs: t.Any) -> None:
        super().__init_subclass__(**kwargs)
        if not issubclass(cls, (InferenceRule, SubproofRule)):
            raise TypeError(f'Final can only be used with subclasses of Rule or SubproofRule (got {cls.__name__})')
        RULES.append(cls)
RULES = list[type[Rule]]()

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

def print_rules_help() -> None:
    print()
    print('## Inference rules:')
    print()
    for rule in RULES:
        if issubclass(rule, InferenceRule):
            print(rule.help())
            print()

    print()
    print('## Subproof rules:')
    print()
    for rule in RULES:
        if issubclass(rule, SubproofRule):
            print(rule.help())
            print()

class RegexRule(SimpleRule):
    NAMES: tuple[str, ...]

    @classmethod
    def match(cls, justification: str) -> t.Self | None:
        names_pattern = '|'.join(re.escape(name.lower()) for name in cls.NAMES)
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

    @classmethod
    def help(cls) -> str:
        rule_strs = []
        for rule_prems, rule_conc in cls.RULES:
            rule_strs.append(
                f"{', '.join([
                     str(ExpressionParser(rule_prem).parse())
                     for rule_prem in rule_prems
                ])} ⊢ {ExpressionParser(rule_conc).parse()}")
        return '\n'.join([
            cls.__name__ + ':',
            '  Rules:',
            *('    ' + rule_str for rule_str in rule_strs),
            '  Justifications:',
            *('    ' + name for name in cls.NAMES),
        ])

class PremiseRule:
    ''' marker class for rules that can be used as premises '''
    pass

class Premise(SimpleRule, Final, PremiseRule):
    RULES = ()

    @classmethod
    def match(cls, justification: str) -> t.Self | None:
        if justification == 'premise' or ('premise'.startswith(justification) and justification.endswith('.')):
            return cls(())
        return None

    @classmethod
    def help(cls) -> str:
        return '\n'.join([
            cls.__name__ + ':',
            '  Rules:',
            '    (none)',
            '  Justifications:',
            '    premise',
            '    prem.',
        ])

class Assumption(SimpleRule, PremiseRule, ABC):
    RULES = ()

    for_short: str
    for_long: str

    @classmethod
    def match(cls, justification: str) -> t.Self | None:
        for_short = cls.for_short.lower()
        for_long = cls.for_long.lower()

        try:
            first_word, rest = justification.split(maxsplit=1)
        except ValueError:
            if justification in (f'a{for_short.replace('.', '')}', f'a.{for_short}'):
                return cls(())
            return None

        if not first_word:
            return None

        if first_word == 'assumption' or ('assumption'.startswith(first_word) and first_word.endswith('.')):
            if rest.replace('for ', '') in (for_short.replace('.', ''), for_short, for_long):
                return cls(())
        return None

    @classmethod
    def help(cls) -> str:
        return '\n'.join([
            cls.__name__ + ':',
            '  Rules:',
            '    (none)',
            '  Justifications:',
            '    assumption for ' + cls.for_long,
            '    assumption for ' + cls.for_short,
            '    A. for ' + cls.for_short,
            '    A.' + cls.for_short,
        ])

class AssumptionForCD(Assumption, Final):
    for_short = 'C.D.'
    for_long = 'conditional derivation'

class AssumptionForID(Assumption, Final):
    for_short = 'I.D.'
    for_long = 'indirect derivation'

class ModusPonens(RegexRule, Final):
    RULES = (
        (
            ('(A -> B)', 'A'),
            'B',
        ),
    )
    NAMES = ('MP', 'M.P.', 'modus ponens')

class ModusTollens(RegexRule, Final):
    RULES = (
        (
            ('(A -> B)', '~B'),
            '~A',
        ),
    )
    NAMES = ('MT', 'M.T.', 'modus tollens')

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
    NAMES = ('DN', 'D.N.', 'double negation')

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
    NAMES = ('DS', 'D.S.', 'disjunctive syllogism')

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
            if m := re.search(r't(\d+)$', justification):
                try:
                    theorem_number = int(m.group(1))
                except ValueError:
                    raise ProofError(f'Invalid theorem number in justification: {justification!r}')
                return cls((), theorem_number=theorem_number)
            return cls((), theorem_number=None)
        return None

    @classmethod
    def help(cls) -> str:
        theorem_strs = []
        for i, theorem in enumerate(THEOREMS, start=1):
            theorem_strs.append(f'T{i}. {ExpressionParser(theorem).parse()}')
        return '\n'.join([
            cls.__name__ + ':',
            '  Allowed theorems:',
            *('    ' + theorem_str for theorem_str in theorem_strs),
            '  Justifications:',
            '    theorem',
            '    theorem: T# (e.g. theorem T1)',
        ])

class ConditionalDerivation(SubproofRule, Final):
    NAMES = ('CD', 'C.D.', 'conditional derivation')

    def check(self, conc: Expr, subproof: Proof) -> None:
        from .proof import Proof

        if not isinstance(conc, Imp):
            raise ProofError(f'Conclusion of conditional derivation must be an implication (got {conc.render()})')

        assumption_line, *_ = subproof.prems
        assumption = assumption_line.expr
        if assumption != conc.left:
            raise ProofError(f'First premise of conditional derivation must match antecedent of conclusion (got {assumption} and {conc.left})')

        *_, consequent_line = subproof.lines
        if isinstance(consequent_line, Proof):
            raise ProofError(f'Last line of conditional derivation cannot be a subproof (got {consequent_line})')

        consequent = consequent_line.expr
        if consequent != conc.right:
            raise ProofError(f'Last premise of conditional derivation must match consequent of conclusion (got {consequent} and {conc.right})')

    @classmethod
    def help(cls) -> str:
        return '\n'.join([
            cls.__name__ + ':',
            '  Justifications:',
            '    conditional derivation',
            '    C.D.',
        ])

class IndirectDerivation(SubproofRule, Final):
    NAMES = ('id', 'i.d.', 'indirect derivation')

    def check(self, conc: Expr, subproof: Proof) -> None:
        from .proof import Proof
        try:
            assumption_line, = subproof.prems
        except ValueError:
            raise ProofError(f'Indirect derivation must have exactly one assumption (got {subproof.prems})')
        assumption = assumption_line.expr

        try:
            *_, contradiction_prem_line, contradiction_negation_line = subproof.lines
        except ValueError:
            raise ProofError(f'Indirect derivation must have at least 2 statements (got {subproof.lines})')
        if isinstance(contradiction_prem_line, Proof):
            raise ProofError(f'Second-last line of indirect derivation cannot be a subproof (got {contradiction_prem_line})')
        if isinstance(contradiction_negation_line, Proof):
            raise ProofError(f'Last line of indirect derivation cannot be a subproof (got {contradiction_negation_line})')
        contradiction_prem = contradiction_prem_line.expr
        contradiction_negation = contradiction_negation_line.expr

        if not isinstance(contradiction_negation, Not):
            raise ProofError(f'Last premise of indirect derivation must be a negation (got {contradiction_negation.render()})')

        if contradiction_prem != contradiction_negation.operand:
            raise ProofError(f'Last premise of indirect derivation must be the negation of the second-last premise (got {contradiction_prem.render()} and {contradiction_negation.operand.render()})')

        if not isinstance(assumption, Not):
            raise ProofError(f'First premise of indirect derivation must be a negation (got {assumption.render()})')

        if assumption.operand != conc:
            raise ProofError(f'First premise of indirect derivation must be the negation of the conclusion (got {assumption.operand.render()} and {conc.render()})')

    @classmethod
    def help(cls) -> str:
        return '\n'.join([
            cls.__name__ + ':',
            '  Justifications:',
            '    indirect derivation',
            '    I.D.',
        ])

class UniversalInstantiation(RegexRule, Final):
    RULES = (
        (
            ('∀xF(x)',),
            'F(a)',
        ),
    )
    NAMES = ('ui', 'u.i.', 'universal instantiation')

    def check(self, conc: Expr, prems: list[Expr]) -> None:
        if len(prems) != 1:
            raise ProofError(f'Universal instantiation must have exactly 1 premise (got {len(prems)})')
        prem, = prems

        if not isinstance(prem, UniversalQuantifier):
            raise ProofError(f'Premise of universal instantiation must be a universal quantifier (got {prem.render()})')

        for term in extract_symbolic_terms(conc):
            replaced_conc = replace_symbolic_term(conc, term, prem.variable)
            if replaced_conc == prem.body:
                return

        raise ProofError(f'No suitable term found to replace with {prem.variable} in conclusion for universal instantiation (got premise {prem.render()} and conclusion {conc.render()})')

class ExistentialGeneralisation(RegexRule, Final):
    RULES = (
        (
            ('F(a)',),
            '∃xF(x)',
        ),
    )
    NAMES = ('eg', 'e.g.', 'existential generalisation', 'existential generalization')

    def check(self, conc: Expr, prems: list[Expr]) -> None:
        if len(prems) != 1:
            raise ProofError(f'Existential generalisation must have exactly 1 premise (got {len(prems)})')
        prem, = prems

        if not isinstance(conc, ExistentialQuantifier):
            raise ProofError(f'Conclusion of existential generalisation must be an existential quantifier (got {conc.render()})')

        for term in extract_symbolic_terms(prem):
            replaced_prem = replace_symbolic_term(prem, term, conc.variable)
            if replaced_prem == conc.body:
                return

        raise ProofError(f'No suitable term found to replace with {conc.variable} in premise for existential generalisation (got premise {prem.render()} and conclusion {conc.render()})')

class ExistentialInstantiation(RegexRule, Final):
    RULES = (
        (
            ('∃xF(x)',),
            'F(a)',
        ),
    )
    NAMES = ('ei', 'e.i.', 'existential instantiation')

    def check(self, conc: Expr, prems: list[Expr]) -> None:
        if len(prems) != 1:
            raise ProofError(f'Existential instantiation must have exactly 1 premise (got {len(prems)})')
        prem, = prems

        if not isinstance(prem, ExistentialQuantifier):
            raise ProofError(f'Premise of existential instantiation must be an existential quantifier (got {prem.render()})')

        for term in extract_symbolic_terms(conc):
            replaced_conc = replace_symbolic_term(conc, term, prem.variable)
            if replaced_conc == prem.body:
                return

        raise ProofError(f'No suitable term found to replace with {prem.variable} in conclusion for existential instantiation (got premise {prem.render()} and conclusion {conc.render()})')

class UniversalDerivation(SubproofRule, Final):
    NAMES = ('ud', 'u.d.', 'universal derivation')

    def check(self, conc: Expr, subproof: Proof) -> None:
        if not isinstance(conc, UniversalQuantifier):
            raise ProofError(f'Conclusion of universal derivation must be a universal quantifier (got {conc.render()})')

        if subproof.arbitrary_term is None:
            raise ProofError(f'Subproof for universal derivation must have an arbitrary term (got {subproof.arbitrary_term})')

        *_, last_line = subproof.lines
        if not hasattr(last_line, 'expr'):
            # can't use isinstance because of circular imports
            raise ProofError(f'Last line of subproof for universal derivation cannot be a subproof (got {last_line})')
        last_expr = last_line.expr

        replaced_last = replace_symbolic_term(last_expr, subproof.arbitrary_term, conc.variable)
        if replaced_last != conc.body:
            raise ProofError(f'Last line of subproof for universal derivation must match body of conclusion after replacing arbitrary term with variable (got {last_expr} -> {replaced_last}, expected {conc.body})')

    @classmethod
    def help(cls) -> str:
        return '\n'.join([
            cls.__name__ + ':',
            '  Justifications:',
            '    universal derivation',
            '    U.D.',
        ])

