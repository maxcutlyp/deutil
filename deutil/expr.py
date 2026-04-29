from __future__ import annotations
from dataclasses import dataclass
from frozendict import frozendict
from abc import ABC, abstractmethod, ABCMeta
from enum import Enum
import inspect
import logging
import typing as t

type PLInterpretation = t.Mapping[Atom, bool]
type FOLInterpretation = t.Mapping[Atom | Predicate, bool]
type Interpretation = PLInterpretation | FOLInterpretation

class _Expr(ABC):
    __match_args__: tuple[str, ...]

    @abstractmethod
    def evaluate(self, interpretation: Interpretation) -> bool:
        raise NotImplementedError
    @abstractmethod
    def render(self) -> str:
        raise NotImplementedError
    @abstractmethod
    def extract[T](self, typ: type[T]) -> set[T]:
        raise NotImplementedError
    def __str__(self) -> str:
        return self.render()
    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({', '.join(f'{arg}={getattr(self, arg)!r}' for arg in self.__match_args__)})"

    def __init_subclass__(cls) -> None:
        sig = inspect.signature(cls.__init__)
        match_args = tuple([param.name for param in sig.parameters.values() if param.name != 'self'])
        setattr(cls, '__match_args__', match_args)

class Atom(_Expr):
    def __init__(self, name: str):
        self.name = name
    def evaluate(self, interpretation: Interpretation) -> bool:
        return interpretation[self]
    def extract[T](self, typ: type[T]) -> set[T]:
        if isinstance(self, typ):
            return {self}
        return set()
    def __hash__(self) -> int:
        return hash(self.name)
    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Atom):
            return NotImplemented
        return self.name == other.name
    def render(self) -> str:
        return self.name
    def __repr__(self) -> str:
        return f"Atom({self.name!r})"

class ArbitraryTermMeta(ABCMeta):
    def __instancecheck__(cls, instance: object) -> bool:
        if SymbolicTerm in instance.__class__.mro():
            return t.cast(SymbolicTerm, instance).is_arbitrary
        return False

class SymbolicTerm(_Expr, metaclass=ArbitraryTermMeta):
    def __init__(self, name: str):
        self.name = name.replace("'", "’")  # normalize to use prime symbol for arbitrary terms
    def evaluate(self, interpretation: Interpretation) -> bool:
        raise SyntaxError('Symbolic terms cannot be evaluated.')
    def extract[T](self, typ: type[T]) -> set[T]:
        if isinstance(self, typ):
            return {self}
        return set()
    def __hash__(self) -> int:
        return hash(self.name)
    def __eq__(self, other: object) -> bool:
        if not isinstance(other, SymbolicTerm):
            return NotImplemented
        return self.name == other.name
    def render(self) -> str:
        return self.name
    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({self.name!r})"

    @property
    def is_arbitrary(self) -> bool:
        return self.name.endswith('’')

class ArbitraryTerm(SymbolicTerm):
    def __init__(self, name: str):
        super().__init__(name)
        if not super().is_arbitrary:
            raise ValueError(f"ArbitraryTerm name must end with a prime symbol, got: {name}")

    @property
    def is_arbitrary(self) -> t.Literal[True]:
        is_arbitrary = super().is_arbitrary
        assert is_arbitrary is True
        return is_arbitrary

class Predicate(_Expr):
    def __init__(self, name: str, arguments: list[SymbolicTerm]):
        self.name = name
        self.arguments = arguments
    def evaluate(self, interpretation: Interpretation) -> bool:
        try:
            return t.cast(FOLInterpretation, interpretation)[self]
        except KeyError:
            raise SyntaxError("Cannot use predicates in truth tables")
    def extract[T](self, typ: type[T]) -> set[T]:
        result = set[T]()
        if isinstance(self, typ):
            result.add(self)
        for arg in self.arguments:
            result |= arg.extract(typ)
        return result
    def __hash__(self) -> int:
        return hash((self.name, tuple(self.arguments)))
    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Predicate):
            return NotImplemented
        return self.name == other.name and self.arguments == other.arguments
    def render(self) -> str:
        args_str = ''.join(arg.render() for arg in self.arguments)
        return f"{self.name}{args_str}" if args_str else self.name

class UnboundPredicate(_Expr):
    def __init__(self, name: str, arity: int):
        self.name = name
        self.arity = arity
    def evaluate(self, interpretation: Interpretation) -> bool:
        raise SyntaxError('Unbound predicates cannot be evaluated.')
    def extract[T](self, typ: type[T]) -> set[T]:
        if isinstance(self, typ):
            return {self}
        return set()
    def __hash__(self) -> int:
        return hash((self.name, self.arity))
    def __eq__(self, other: object) -> bool:
        if not isinstance(other, UnboundPredicate):
            return NotImplemented
        return self.name == other.name and self.arity == other.arity
    def render(self) -> str:
        return f"{self.name}/{self.arity}"

    @classmethod
    def from_predicate(cls, predicate: Predicate) -> UnboundPredicate:
        return cls(predicate.name, len(predicate.arguments))

    def bind(self, arguments: t.Sequence[SymbolicTerm]) -> Predicate:
        if len(arguments) != self.arity:
            raise ValueError(f"Expected {self.arity} arguments to bind predicate {self.name}, got {len(arguments)}")
        return Predicate(self.name, list(arguments))

class Quantifier(_Expr):
    def __init__(self, variable: SymbolicTerm, body: Expr):
        self.variable = variable
        self.body = body
    def extract[T](self, typ: type[T]) -> set[T]:
        result = set[T]()
        if isinstance(self, typ):
            result.add(self)
        result |= self.variable.extract(typ)
        result |= self.body.extract(typ)
        return result
    def __eq__(self, other: object) -> bool:
        if type(self) != type(other):
            return NotImplemented
        assert isinstance(other, Quantifier)
        return self.variable == other.variable and self.body == other.body
    def __hash__(self) -> int:
        return hash((type(self), self.variable, self.body))

class UniversalQuantifier(Quantifier):
    def evaluate(self, interpretation: Interpretation) -> bool:
        return all(
            replace_symbolic_term(self.body, self.variable, term).evaluate(interpretation)
            for term in domain(interpretation)
        )
    def render(self) -> str:
        return f"{StaticToken.UNIVERSAL.value}{self.variable.render()}{self.body.render()}"

class ExistentialQuantifier(Quantifier):
    def evaluate(self, interpretation: Interpretation) -> bool:
        return any(
            replace_symbolic_term(self.body, self.variable, term).evaluate(interpretation)
            for term in domain(interpretation)
        )
    def render(self) -> str:
        return f"{StaticToken.EXISTENTIAL.value}{self.variable.render()}{self.body.render()}"

class BinaryOperator(_Expr):
    def __init__(self, left: Expr, right: Expr):
        self.left = left
        self.right = right

    def __eq__(self, other: object) -> bool:
        if type(self) != type(other):
            return NotImplemented
        assert isinstance(other, BinaryOperator)
        return self.left == other.left and self.right == other.right

    def __hash__(self) -> int:
        return hash((type(self), self.left, self.right))

    def evaluate(self, interpretation: Interpretation) -> bool:
        left_value = self.left.evaluate(interpretation)
        right_value = self.right.evaluate(interpretation)
        return self._evaluate(left_value, right_value)

    def extract[T](self, typ: type[T]) -> set[T]:
        result = set[T]()
        if isinstance(self, typ):
            result.add(self)
        result |= self.left.extract(typ)
        result |= self.right.extract(typ)
        return result

    @abstractmethod
    def _evaluate(self, left_value: bool, right_value: bool) -> bool:
        raise NotImplementedError

class UnaryOperator(_Expr):
    def __init__(self, operand: Expr):
        self.operand = operand

    def __eq__(self, other: object) -> bool:
        if type(self) != type(other):
            return NotImplemented
        assert isinstance(other, UnaryOperator)
        return self.operand == other.operand

    def __hash__(self) -> int:
        return hash((type(self), self.operand))

    def evaluate(self, interpretation: Interpretation) -> bool:
        operand_value = self.operand.evaluate(interpretation)
        return self._evaluate(operand_value)

    def extract[T](self, typ: type[T]) -> set[T]:
        result = set[T]()
        if isinstance(self, typ):
            result.add(self)
        result |= self.operand.extract(typ)
        return result

    @abstractmethod
    def _evaluate(self, operand_value: bool) -> bool:
        raise NotImplementedError

class MetaFunction(_Expr):
    def __init__(self, name: str, argument: SymbolicTerm):
        self.name = name
        self.argument = argument
    def evaluate(self, interpretation: Interpretation) -> bool:
        raise SyntaxError('MetaFunctions cannot be evaluated.')
    def extract[T](self, typ: type[T]) -> set[T]:
        result = set[T]()
        if isinstance(self, typ):
            result.add(self)
        result |= self.argument.extract(typ)
        return result
    def __hash__(self) -> int:
        return hash((self.name, self.argument))
    def __eq__(self, other: object) -> bool:
        if not isinstance(other, MetaFunction):
            return NotImplemented
        return self.name == other.name and self.argument == other.argument
    def render(self) -> str:
        return f"{self.name}({self.argument.render()})"

type Expr = Atom | Predicate | Quantifier | BinaryOperator | UnaryOperator | MetaFunction

class And(BinaryOperator):
    def _evaluate(self, left_value: bool, right_value: bool) -> bool:
        return left_value and right_value
    def render(self) -> str:
        return f"({self.left.render()} {StaticToken.AND.value} {self.right.render()})"

class Or(BinaryOperator):
    def _evaluate(self, left_value: bool, right_value: bool) -> bool:
        return left_value or right_value
    def render(self) -> str:
        return f"({self.left.render()} {StaticToken.OR.value} {self.right.render()})"

class Imp(BinaryOperator):
    def _evaluate(self, left_value: bool, right_value: bool) -> bool:
        return not left_value or right_value
    def render(self) -> str:
        return f"({self.left.render()} {StaticToken.IMP.value} {self.right.render()})"

class Bij(BinaryOperator):
    def _evaluate(self, left_value: bool, right_value: bool) -> bool:
        return left_value == right_value
    def render(self) -> str:
        return f"({self.left.render()} {StaticToken.BIJ.value} {self.right.render()})"

class Not(UnaryOperator):
    def _evaluate(self, operand_value: bool) -> bool:
        return not operand_value
    def render(self) -> str:
        return f"{StaticToken.NOT.value}{self.operand.render()}"

def extract_atoms(expr: Expr) -> set[Atom]:
    ''' deprecated - use expr.extract(Atom) instead '''
    return expr.extract(Atom)

def extract_metafuncs(expr: Expr) -> set[MetaFunction]:
    ''' deprecated - use expr.extract(MetaFunction) instead '''
    return expr.extract(MetaFunction)

def extract_symbolic_terms(expr: Expr) -> set[SymbolicTerm]:
    ''' deprecated - use expr.extract(SymbolicTerm) instead '''
    return expr.extract(SymbolicTerm)

def domain(interpretation: Interpretation) -> set[SymbolicTerm]:
    terms = set[SymbolicTerm]()
    for key in interpretation.keys():
        terms |= key.extract(SymbolicTerm)
    return terms

@t.overload
def replace_symbolic_term[TOld: SymbolicTerm, TNew: SymbolicTerm](expr: TOld, old: TOld, new: TNew) -> TNew: ...
@t.overload
def replace_symbolic_term[T: _Expr](expr: T, old: SymbolicTerm, new: SymbolicTerm) -> T: ...
def replace_symbolic_term[T: _Expr](expr: T, old: SymbolicTerm, new: SymbolicTerm) -> _Expr:
    if expr == old:
        return new
    if isinstance(expr, _Expr):
        new_args = dict[str, t.Any]()
        for argname in expr.__match_args__:
            old_arg = getattr(expr, argname)
            new_arg = replace_symbolic_term(old_arg, old, new)
            new_args[argname] = new_arg
        return type(expr)(**new_args)
    if isinstance(expr, t.Iterable) and not isinstance(expr, str):
        return type(expr)(replace_symbolic_term(elem, old, new) for elem in expr)
    return expr

class StaticToken(Enum):
    LPAREN = '('
    RPAREN = ')'
    AND = '∧'
    OR = '∨'
    IMP = '→'
    BIJ = '↔'
    NOT = '¬'
    UNIVERSAL = '∀'
    EXISTENTIAL = '∃'

class DynamicToken:
    def __init__(self, value: str):
        self.value = value
    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({self.value!r})"

class AtomOrPredicateOrMetaFunctionToken(DynamicToken):
    pass

class SymbolicTermToken(DynamicToken):
    pass

type AnyToken = StaticToken | DynamicToken

TOKENS = {
    **({token.value : token for token in StaticToken}),

    # Allow for ASCII alternatives
    '~': StaticToken.NOT,
    '&': StaticToken.AND,
    '^': StaticToken.AND,
    '|': StaticToken.OR,
    'v': StaticToken.OR,
    '->': StaticToken.IMP,
    '<->': StaticToken.BIJ,
    '\\V': StaticToken.UNIVERSAL,
    '\\E': StaticToken.EXISTENTIAL,
}

class EndOfExpression(Exception):
    pass

class ExpressionTokenizer:
    def __init__(self, expr: str):
        self.expr = expr
        self.pos = 0

    def next_token(self) -> AnyToken:
        token, skip = self._peek_token()
        self.pos += skip
        return token

    def _peek_token(self) -> tuple[AnyToken, int]:
        token_width = 1
        pos = self.pos
        while True:
            if pos >= len(self.expr):
                raise EndOfExpression

            if pos + token_width > len(self.expr):
                raise EndOfExpression

            c = self.expr[pos]
            if c.isspace():
                pos += 1
                continue

            token_str = self.expr[pos : pos + token_width]
            if token_str in TOKENS:
                break

            if c.isupper():
                return AtomOrPredicateOrMetaFunctionToken(c), 1 + (pos - self.pos)

            if c.islower():
                arbitrary_term = self.expr[pos : pos + 2]
                if len(arbitrary_term) == 2 and arbitrary_term[-1:] in ("'’"):
                    # force arbitrary terms to be rendered with a prime symbol, even if the input uses a straight apostrophe
                    return SymbolicTermToken(arbitrary_term[:-1] + '’'), 2 + (pos - self.pos)
                return SymbolicTermToken(c), 1 + (pos - self.pos)

            token_width += 1

        return TOKENS[token_str], token_width + (pos - self.pos)

    def peek_token(self) -> AnyToken:
        token, _ = self._peek_token()
        return token

    def peek_token_or_none(self) -> AnyToken | None:
        try:
            return self.peek_token()
        except EndOfExpression:
            return None

    def __iter__(self) -> t.Iterator[AnyToken]:
        return self
    def __next__(self) -> AnyToken:
        try:
            return self.next_token()
        except EndOfExpression:
            raise StopIteration

    def print_state(self) -> None:
        logging.debug(f'{self.expr}\n{" " * self.pos}^')

class ExpressionParser:
    def __init__(self, expr: str, raise_on_extra_tokens: bool = False):
        self.tokens = ExpressionTokenizer(expr)

    def parse(self) -> Expr:
        expr = self._parse()
        try:
            extra_token = self.tokens.next_token()
            raise SyntaxError(f"Unexpected token after end of expression: {extra_token} at position {self.tokens.pos} (parsed: {expr})")
        except EndOfExpression:
            pass
        return expr

    def _parse(self) -> Expr:
        for token in self.tokens:
            logging.debug(f'Parsing token: {token}')
            self.tokens.print_state()
            if isinstance(token, DynamicToken):
                return self._parse_dynamic_token(token)
            elif token == StaticToken.LPAREN:
                return self._parse_binary()
            elif token == StaticToken.NOT:
                return self._parse_unary()
            elif token in {StaticToken.UNIVERSAL, StaticToken.EXISTENTIAL}:
                return self._parse_quantifier(token)
            else:
                raise SyntaxError(f"Unexpected token: {token} at position {self.tokens.pos}")
        raise SyntaxError("Unexpected end of expression")

    def _parse_dynamic_token(self, token: DynamicToken) -> Expr:
        if isinstance(token, AtomOrPredicateOrMetaFunctionToken):
            return self._parse_atom_or_predicate_or_metafunction(token)
        elif isinstance(token, SymbolicTermToken):
            raise SyntaxError(f"Unexpected symbolic term: {token} at position {self.tokens.pos}")
        else:
            raise SyntaxError(f"Unknown dynamic token: {token} at position {self.tokens.pos}")

    def _parse_atom_or_predicate_or_metafunction(self, token: AtomOrPredicateOrMetaFunctionToken) -> Expr:
        peek = self.tokens.peek_token_or_none()

        if isinstance(peek, SymbolicTermToken):
            # Predicate with arguments
            arguments = list[SymbolicTerm]()
            while isinstance((peek := self.tokens.peek_token_or_none()), SymbolicTermToken):
                symbolic_term = self.tokens.next_token()
                assert isinstance(symbolic_term, SymbolicTermToken), f'mismatch between peeked token and next token: {peek} vs {symbolic_term}'
                arguments.append(SymbolicTerm(symbolic_term.value))
            return Predicate(token.value, arguments)

        if peek == StaticToken.LPAREN:
            # Metafunction - assume exactly one argument
            self.tokens.next_token()  # consume '('
            variable = self.tokens.next_token()
            if not isinstance(variable, SymbolicTermToken):
                raise SyntaxError(f"Expected variable after metafunction name, got: {variable} at position {self.tokens.pos}")
            if self.tokens.next_token() != StaticToken.RPAREN:
                raise SyntaxError(f"Expected ')' after metafunction variable, got: {self.tokens.peek_token()} at position {self.tokens.pos}")
            return MetaFunction(token.value, SymbolicTerm(variable.value))

        return Atom(token.value)

    def _parse_quantifier(self, quantifier: StaticToken) -> Expr:
        logging.debug(f"Parsing quantifier: {quantifier}")
        token = self.tokens.next_token()
        logging.debug(f"Parsed variable: {token}")
        if not isinstance(token, SymbolicTermToken):
            raise SyntaxError(f"Expected variable after quantifier, got: {token} at position {self.tokens.pos}")
        variable = SymbolicTerm(token.value)
        body = self._parse()
        if quantifier == StaticToken.UNIVERSAL:
            return UniversalQuantifier(variable, body)
        elif quantifier == StaticToken.EXISTENTIAL:
            return ExistentialQuantifier(variable, body)
        else:
            raise SyntaxError(f"Unknown quantifier: {quantifier}")

    def _parse_binary(self) -> Expr:
        logging.debug("Parsing binary operator")
        left = self._parse()
        logging.debug(f"Parsed left operand: {left}")
        operator = self.tokens.next_token()
        logging.debug(f'Parsed operator: {operator}')
        self.tokens.print_state()
        if operator not in {StaticToken.AND, StaticToken.OR, StaticToken.IMP, StaticToken.BIJ}:
            raise SyntaxError(f"Expected binary operator, got: {operator}")
        right = self._parse()
        logging.debug(f"Parsed right operand: {right}")
        try:
            if (found := self.tokens.next_token()) != StaticToken.RPAREN:
                raise SyntaxError(f"Expected ')', got {found}")
        except EndOfExpression:
            raise SyntaxError("Expected ')' at end of expression")
        if operator == StaticToken.AND:
            return And(left, right)
        elif operator == StaticToken.OR:
            return Or(left, right)
        elif operator == StaticToken.IMP:
            return Imp(left, right)
        elif operator == StaticToken.BIJ:
            return Bij(left, right)
        raise SyntaxError(f"Unknown operator: {operator}")

    def _parse_unary(self) -> Expr:
        operand = self._parse()
        return Not(operand)


def new_metafunc_name(*exprs: Expr) -> str:
    existing_names = set(mf.name for expr in exprs for mf in extract_metafuncs(expr))
    i = 1
    while True:
        name = f'__MF{i}__'
        if name not in existing_names:
            return name
        i += 1

def new_variable(*exprs: Expr) -> SymbolicTerm:
    existing_names = set(term for expr in exprs for term in extract_symbolic_terms(expr))
    i = 1
    while True:
        name = f'__var{i}__'
        if name not in existing_names:
            return SymbolicTerm(name)
        i += 1

DO_UNIFY_DEBUG = False
def unify(expr1: Expr, expr2: Expr, bindings: dict[Atom, Expr] | None = None) -> dict[Atom, Expr] | None:
    def debug(*args: t.Any) -> None:
        if DO_UNIFY_DEBUG:
            print(*args)

    if bindings is None:
        bindings = {}

    debug(f'Unifying {expr1.render()} and {expr2.render()} with bindings {bindings}')
    if isinstance(expr1, Atom):
        if expr1 in bindings:
            debug(f'Atom {expr1.render()} is already bound to {bindings[expr1].render()}, checking if it matches {expr2.render()}')
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
