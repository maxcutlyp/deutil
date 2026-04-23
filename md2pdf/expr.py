from __future__ import annotations
from dataclasses import dataclass
from frozendict import frozendict
from abc import ABC, abstractmethod
from enum import Enum
import inspect
import logging
import typing as t

class _Expr(ABC):
    __match_args__: tuple[str, ...]

    @abstractmethod
    def evaluate(self, assignments: t.Mapping[Atom, bool]) -> bool:
        raise NotImplementedError
    @abstractmethod
    def render(self) -> str:
        raise NotImplementedError
    def __str__(self) -> str:
        return self.render()
    def __repr__(self) -> str:
        return str(self)

    def __init_subclass__(cls) -> None:
        sig = inspect.signature(cls.__init__)
        match_args = tuple([param.name for param in sig.parameters.values() if param.name != 'self'])
        setattr(cls, '__match_args__', match_args)

class Atom(_Expr):
    def __init__(self, name: str):
        self.name = name
    def evaluate(self, assignments: t.Mapping[Atom, bool]) -> bool:
        return assignments[self]
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

class SymbolicTerm(_Expr):
    def __init__(self, name: str):
        self.name = name
    def evaluate(self, assignments: t.Mapping[Atom, bool]) -> bool:
        raise NotImplementedError("Evaluation of symbolic terms is not implemented yet")
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

class Variable(SymbolicTerm):
    pass
class DefiniteName(SymbolicTerm):
    pass
# TODO: Indefinite names, arbitrary terms

class Argument(SymbolicTerm):
    pass

class Predicate(_Expr):
    def __init__(self, name: str, arguments: list[Argument]):
        self.name = name
        self.arguments = arguments
    def evaluate(self, assignments: t.Mapping[Atom, bool]) -> bool:
        raise NotImplementedError("Evaluation of predicates is not implemented yet")
    def __hash__(self) -> int:
        return hash((self.name, tuple(self.arguments)))
    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Predicate):
            return NotImplemented
        return self.name == other.name and self.arguments == other.arguments
    def render(self) -> str:
        args_str = ''.join(arg.render() for arg in self.arguments)
        return f"{self.name}{args_str}" if args_str else self.name

class Quantifier(_Expr):
    def __init__(self, variable: Variable, body: Expr):
        self.variable = variable
        self.body = body
    def __eq__(self, other: object) -> bool:
        if type(self) != type(other):
            return NotImplemented
        assert isinstance(other, Quantifier)
        return self.variable == other.variable and self.body == other.body
    def __hash__(self) -> int:
        return hash((type(self), self.variable, self.body))

class UniversalQuantifier(Quantifier):
    def evaluate(self, assignments: t.Mapping[Atom, bool]) -> bool:
        raise NotImplementedError("Evaluation of quantifiers not implemented yet")
    def render(self) -> str:
        return f"{StaticToken.UNIVERSAL.value}{self.variable.render()}{self.body.render()}"

class ExistentialQuantifier(Quantifier):
    def evaluate(self, assignments: t.Mapping[Atom, bool]) -> bool:
        raise NotImplementedError("Evaluation of quantifiers not implemented yet")
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

    def evaluate(self, assignments: t.Mapping[Atom, bool]) -> bool:
        left_value = self.left.evaluate(assignments)
        right_value = self.right.evaluate(assignments)
        return self._evaluate(left_value, right_value)

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

    def evaluate(self, assignments: t.Mapping[Atom, bool]) -> bool:
        operand_value = self.operand.evaluate(assignments)
        return self._evaluate(operand_value)

    @abstractmethod
    def _evaluate(self, operand_value: bool) -> bool:
        raise NotImplementedError

class MetaFunction(_Expr):
    def __init__(self, name: str, argument: Variable):
        self.name = name
        self.argument = argument
    def evaluate(self, assignments: t.Mapping[Atom, bool]) -> bool:
        raise NotImplementedError("Evaluation of metafunctions not implemented yet")
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
    if isinstance(expr, Atom):
        return {expr}
    elif isinstance(expr, Predicate):
        return set()
    elif isinstance(expr, Quantifier):
        return extract_atoms(expr.body)
    elif isinstance(expr, BinaryOperator):
        return extract_atoms(expr.left) | extract_atoms(expr.right)
    elif isinstance(expr, UnaryOperator):
        return extract_atoms(expr.operand)
    elif isinstance(expr, MetaFunction):
        return set()

def extract_metafuncs(expr: Expr) -> set[MetaFunction]:
    if isinstance(expr, Atom):
        return set()
    elif isinstance(expr, Predicate):
        return set()
    elif isinstance(expr, Quantifier):
        return extract_metafuncs(expr.body)
    elif isinstance(expr, BinaryOperator):
        return extract_metafuncs(expr.left) | extract_metafuncs(expr.right)
    elif isinstance(expr, UnaryOperator):
        return extract_metafuncs(expr.operand)
    elif isinstance(expr, MetaFunction):
        return {expr}

def extract_symbolic_terms(expr: Expr) -> set[SymbolicTerm]:
    if isinstance(expr, Atom):
        return set()
    elif isinstance(expr, Predicate):
        return set(expr.arguments)
    elif isinstance(expr, Quantifier):
        return {expr.variable} | extract_symbolic_terms(expr.body)
    elif isinstance(expr, BinaryOperator):
        return extract_symbolic_terms(expr.left) | extract_symbolic_terms(expr.right)
    elif isinstance(expr, UnaryOperator):
        return extract_symbolic_terms(expr.operand)
    elif isinstance(expr, MetaFunction):
        return {expr.argument}

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

type TTRowAssignment = frozendict[Atom, bool]
type TTRowResult = t.OrderedDict[Expr, bool]
type TruthTable = t.Mapping[TTRowAssignment, TTRowResult]

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
            arguments = list[Argument]()
            while isinstance((peek := self.tokens.peek_token_or_none()), SymbolicTermToken):
                symbolic_term = self.tokens.next_token()
                assert isinstance(symbolic_term, SymbolicTermToken), f'mismatch between peeked token and next token: {peek} vs {symbolic_term}'
                arguments.append(Argument(symbolic_term.value))
            return Predicate(token.value, arguments)

        if peek == StaticToken.LPAREN:
            # Metafunction - assume exactly one argument
            self.tokens.next_token()  # consume '('
            variable = self.tokens.next_token()
            if not isinstance(variable, SymbolicTermToken):
                raise SyntaxError(f"Expected variable after metafunction name, got: {variable} at position {self.tokens.pos}")
            if self.tokens.next_token() != StaticToken.RPAREN:
                raise SyntaxError(f"Expected ')' after metafunction variable, got: {self.tokens.peek_token()} at position {self.tokens.pos}")
            return MetaFunction(token.value, Variable(variable.value))

        return Atom(token.value)

    def _parse_quantifier(self, quantifier: StaticToken) -> Expr:
        logging.debug(f"Parsing quantifier: {quantifier}")
        token = self.tokens.next_token()
        logging.debug(f"Parsed variable: {token}")
        if not isinstance(token, SymbolicTermToken):
            raise SyntaxError(f"Expected variable after quantifier, got: {token} at position {self.tokens.pos}")
        variable = Variable(token.value)
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

def new_variable(*exprs: Expr) -> Variable:
    existing_names = set(term for expr in exprs for term in extract_symbolic_terms(expr))
    i = 1
    while True:
        name = f'__var{i}__'
        if name not in existing_names:
            return Variable(name)
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

# def unify(expr1: Expr, expr2: Expr, bindings: dict[Atom, Expr] | None = None) -> dict[Atom, Expr] | None:
#     def debug(*args: t.Any) -> None:
#         if DO_UNIFY_DEBUG:
#             print(*args)
# 
#     if bindings is None:
#         bindings = {}
# 
#     debug(f'Unifying {expr1.render()} and {expr2.render()} with bindings {bindings}')
#     if isinstance(expr1, Atom):
#         if expr1 in bindings:
#             if bindings[expr1] == expr2:
#                 return bindings
#             return None
#         else:
#             bindings[expr1] = expr2
#             return bindings
# 
#     elif isinstance(expr1, MetaFunction):
#         if isinstance(expr2, Atom):
#             return None
#         if isinstance(expr2, Predicate):
#             for expr2_argument in expr2.arguments:
#                 bindings[expr1.argument] = expr2_argument
#                 if (new_bindings := unify(expr1, expr2_argument, bindings)) is not None:
#                     return new_bindings
#         if isinstance(expr2, Quantifier):
#             ...
#         if isinstance(expr2, UnaryOperator):
#             new_operand = MetaFunction(new_metafunc_name(expr1, expr2), new_variable(expr1, expr2))
#             return unify(new_operand, expr2.operand, bindings)
#         if isinstance(expr2, BinaryOperator):
#             new_left = MetaFunction(new_metafunc_name(expr1, expr2), new_variable(expr1, expr2))
#             new_right = MetaFunction(new_metafunc_name(expr1, expr2, new_left), new_variable(expr1, expr2, new_left))
#             bindings_left = unify(new_left, expr2.left, bindings)
#             if bindings_left is None:
#                 return None
#             bindings_right = unify(new_right, expr2.right, bindings_left)
#             if bindings_right is None:
#                 return None
#             return bindings_left | bindings_right
#         if isinstance(expr2, MetaFunction):
#             raise NotImplementedError("Unification of metafunctions not implemented")
# 
#     elif type(expr1) != type(expr2):
#         return None
# 
#     elif isinstance(expr1, UnaryOperator):
#         if not isinstance(expr2, UnaryOperator):
#             return None
#         return unify(expr1.operand, expr2.operand, bindings)
# 
#     elif isinstance(expr1, BinaryOperator):
#         if not isinstance(expr2, BinaryOperator):
#             return None
#         bindings_left = unify(expr1.left, expr2.left, bindings)
#         if bindings_left is None:
#             return None
#         return unify(expr1.right, expr2.right, bindings_left)
# 
#     else:
#         raise ValueError(f'Unknown expression type: {type(expr1)}')
# 
