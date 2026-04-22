from __future__ import annotations
from frozendict import frozendict
from abc import ABC, abstractmethod
from enum import Enum
import logging
import typing as t

class _Expr(ABC):
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

type Expr = Atom | BinaryOperator | UnaryOperator

class And(BinaryOperator):
    def _evaluate(self, left_value: bool, right_value: bool) -> bool:
        return left_value and right_value
    def render(self) -> str:
        return f"({self.left.render()} {Token.AND.value} {self.right.render()})"

class Or(BinaryOperator):
    def _evaluate(self, left_value: bool, right_value: bool) -> bool:
        return left_value or right_value
    def render(self) -> str:
        return f"({self.left.render()} {Token.OR.value} {self.right.render()})"

class Imp(BinaryOperator):
    def _evaluate(self, left_value: bool, right_value: bool) -> bool:
        return not left_value or right_value
    def render(self) -> str:
        return f"({self.left.render()} {Token.IMP.value} {self.right.render()})"

class Bij(BinaryOperator):
    def _evaluate(self, left_value: bool, right_value: bool) -> bool:
        return left_value == right_value
    def render(self) -> str:
        return f"({self.left.render()} {Token.BIJ.value} {self.right.render()})"

class Not(UnaryOperator):
    def _evaluate(self, operand_value: bool) -> bool:
        return not operand_value
    def render(self) -> str:
        return f"{Token.NOT.value}{self.operand.render()}"

def extract_atoms(expr: Expr) -> set[Atom]:
    if isinstance(expr, Atom):
        return {expr}
    elif isinstance(expr, BinaryOperator):
        return extract_atoms(expr.left) | extract_atoms(expr.right)
    elif isinstance(expr, UnaryOperator):
        return extract_atoms(expr.operand)

type TTRowAssignment = frozendict[Atom, bool]
type TTRowResult = t.OrderedDict[Expr, bool]
type TruthTable = t.Mapping[TTRowAssignment, TTRowResult]

class Token(Enum):
    LPAREN = '('
    RPAREN = ')'
    AND = '∧'
    OR = '∨'
    IMP = '→'
    BIJ = '↔'
    NOT = '¬'

class AtomToken:
    def __init__(self, name: str):
        self.name = name
    def __repr__(self) -> str:
        return f"AtomToken({self.name!r})"

TOKENS = {
    **({token.value : token for token in Token}),

    # Allow for ASCII alternatives
    '~': Token.NOT,
    '&': Token.AND,
    '^': Token.AND,
    '|': Token.OR,
    'v': Token.OR,
    '->': Token.IMP,
    '<->': Token.BIJ,
}

class EndOfExpression(Exception):
    pass

class ExpressionTokenizer:
    def __init__(self, expr: str):
        self.expr = expr
        self.pos = 0

    def next_token(self) -> Token | AtomToken:
        token, skip = self._peek_token()
        self.pos += skip
        return token

    def _peek_token(self) -> tuple[Token | AtomToken, int]:
        token_width = 0
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

            if c.isupper():
                return AtomToken(c), 1 + (pos - self.pos)

            token_str = self.expr[pos : pos + token_width]
            if token_str in TOKENS:
                break

            token_width += 1

        return TOKENS[token_str], token_width + (pos - self.pos)

    def peek_token(self) -> Token | AtomToken:
        token, _ = self._peek_token()
        return token

    def __iter__(self) -> t.Iterator[Token | AtomToken]:
        return self
    def __next__(self) -> Token | AtomToken:
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
            raise SyntaxError(f"Unexpected token after end of expression: {extra_token} at position {self.tokens.pos}")
        except EndOfExpression:
            pass
        return expr

    def _parse(self) -> Expr:
        for token in self.tokens:
            logging.debug(f'Parsing token: {token}')
            self.tokens.print_state()
            if isinstance(token, AtomToken):
                return Atom(token.name)
            elif token == Token.LPAREN:
                return self._parse_binary()
            elif token == Token.NOT:
                return self._parse_unary()
            else:
                raise SyntaxError(f"Unexpected token: {token} at position {self.tokens.pos}")
        raise SyntaxError("Unexpected end of expression")

    def _parse_binary(self) -> Expr:
        logging.debug("Parsing binary operator")
        left = self._parse()
        logging.debug(f"Parsed left operand: {left}")
        operator = self.tokens.next_token()
        logging.debug(f'Parsed operator: {operator}')
        self.tokens.print_state()
        if operator not in {Token.AND, Token.OR, Token.IMP, Token.BIJ}:
            raise SyntaxError(f"Expected binary operator, got: {operator}")
        right = self._parse()
        logging.debug(f"Parsed right operand: {right}")
        try:
            if (found := self.tokens.next_token()) != Token.RPAREN:
                raise SyntaxError(f"Expected ')', got {found}")
        except EndOfExpression:
            raise SyntaxError("Expected ')' at end of expression")
        if operator == Token.AND:
            return And(left, right)
        elif operator == Token.OR:
            return Or(left, right)
        elif operator == Token.IMP:
            return Imp(left, right)
        elif operator == Token.BIJ:
            return Bij(left, right)
        raise SyntaxError(f"Unknown operator: {operator}")

    def _parse_unary(self) -> Expr:
        operand = self._parse()
        return Not(operand)

