from __future__ import annotations
import re
import typing as t
import xml.etree.ElementTree as etree
import logging

from .expr import (
    Expr,
    ExpressionParser,
    EndOfExpression,
    ArbitraryTerm,
    SymbolicTerm,
    extract_symbolic_terms,
)

from .rules import (
    find_rule,
    ProofError,
    InferenceRule,
    SubproofRule,
    PremiseRule,
    Premise,
)

class ProofLine:
    num: int
    expr: Expr
    justification: str
    def __init__(self, num: int, expr: Expr, justification: str):
        self.num = num
        self.expr = expr
        self.justification = justification
    def __str__(self) -> str:
        return f'{self.num}. {self.expr.render()}  {self.justification}'

class Proof:
    prems: list[ProofLine]
    lines: list[ProofLine | Proof]
    start: int
    end: int
    level: int
    parent: Proof | None
    arbitrary_term: ArbitraryTerm | None

    def __init__(
        self,
        prems: list[ProofLine],
        lines: list[ProofLine | Proof],
        start: int,
        end: int,
        level: int,
        arbitrary_term: ArbitraryTerm | None,
    ):
        self.prems = prems
        self.lines = lines
        self.start = start
        self.end = end
        self.level = level
        self.arbitrary_term = arbitrary_term
        self.parent = None

    def __str__(self) -> str:
        indent = '| ' * self.level
        prems_str = '\n'.join(indent + str(prem) for prem in self.prems)
        lines_str = '\n'.join(('' if isinstance(line, Proof) else indent) + str(line) for line in self.lines)
        return '\n'.join([
            prems_str,
            indent.strip() + '-',
            lines_str,
        ])

    @classmethod
    def from_markdown(cls, rawlines: list[str], level: int = 1) -> Proof:
        p, _ = cls._from_markdown(rawlines, level)
        return p

    @classmethod
    def _from_markdown(cls, rawlines: list[str], level: int) -> tuple[Proof, int]:
        prems = list[ProofLine]()
        lines = list[ProofLine | Proof]()
        curr: list[ProofLine] | list[ProofLine | Proof] = prems

        arbitrary_term: ArbitraryTerm | None = None

        i = 0
        while i < len(rawlines):
            line = rawlines[i].strip()
            i += 1
            if not line:
                continue
            if not line.startswith('|'):
                continue

            logging.debug(f'Parsing line {i}: {line} ({level=})')
            if m := re.match(rf'^{r'\|\s*' * level}', line):
                trimmed = line[m.end():]
                logging.debug(f'Trimmed line: {trimmed}')
                if trimmed.startswith('|'):
                    logging.debug(f'Start of subproof detected on line {i}, parsing subproof...')
                    subproof, skip = cls._from_markdown(rawlines[i-1:], level + 1)
                    logging.debug(f'Finished parsing subproof starting on line {i}, skipping {skip} lines')
                    i += skip - 2
                    lines.append(subproof)
                    continue
            else:
                # end of (sub)proof
                break

            if trimmed.startswith('-'):
                curr = lines
                continue

            if m := re.match(r'^(\d+)\.\s*(.+)\s\s+(.*)$', trimmed):
                num, expr_str, justification = m.groups()
                parser = ExpressionParser(expr_str, raise_on_extra_tokens=True)

                try:
                    expr = parser.parse()
                except SyntaxError as e:
                    raise SyntaxError(f'Error parsing expression on line {num}: {e}')
                except EndOfExpression:
                    raise SyntaxError(f'Unexpected end of expression on line {num}')

                curr.append(ProofLine(int(num), expr, justification))
                continue

            if m := re.match(r"^\[([a-z]['’])\]", trimmed):
                # defining an arbitrary term
                if level == 1:
                    raise SyntaxError(f'Arbitrary terms can only be defined in subproofs (line {i})')
                if curr is lines or (curr is prems and prems):
                    raise SyntaxError(f'Arbitrary term definition must be the first line of a subproof (line {i})')
                if arbitrary_term is not None:
                    raise SyntaxError(f'Multiple arbitrary terms defined in the same proof (line {i})')
                arbitrary_term = ArbitraryTerm(m.group(1).replace("'", '’'))  # replace straight quote with prime symbol

                continue

            raise SyntaxError(f'Invalid proof line on line {i+1}: {line}')
        else:
            if level > 1:
                raise SyntaxError(f'Final line of proof cannot be a subproof')

        inst = cls(
            prems,
            lines,
            start=(
                prems[0].num if prems
                else (
                    lines[0].start
                    if isinstance(lines[0], Proof)
                    else lines[0].num
                )
                if lines
                else 0
            ),
            end=(
                (
                    lines[-1].end
                    if isinstance(lines[-1], Proof)
                    else lines[-1].num
                )
                if lines
                else prems[-1].num if prems
                else 0
            ),
            level=level,
            arbitrary_term=arbitrary_term,
        )

        for l in lines:
            if isinstance(l, Proof):
                l.parent = inst

        return inst, i

    @property
    def maxdepth(self) -> int:
        if self.parent:
            return self.parent.maxdepth
        return self._maxdepth

    @property
    def _maxdepth(self) -> int:
        if not self.lines:
            return self.level

        return max(
            line._maxdepth
            if isinstance(line, Proof)
            else self.level
            for line in self.lines
        )

    def _to_rows(self) -> t.Iterable[etree.Element]:
        colspan = self.maxdepth - self.level + 1

        def _row(line: ProofLine | None) -> etree.Element:
            row = etree.Element('tr')

            for _ in range(self.level - 1):
                fitch_cell = etree.SubElement(row, 'td')
                fitch_cell.set('class', 'border-left')

            content_cell = etree.SubElement(row, 'td')
            content_cell.set('colspan', str(colspan))
            content_cell.set('class', 'border-left')
            just_cell = etree.SubElement(row, 'td')
            if line is not None:
                content_cell.text = f'{line.num}. {line.expr.render()}'
                just_cell.text = line.justification

            return row

        if self.arbitrary_term:
            atd_row = _row(None)
            atd_cell = atd_row.find('td[@colspan]')
            assert atd_cell is not None
            atd_box = etree.SubElement(atd_cell, 'span', {'class': 'arbitrary-term'})
            atd_box.text = self.arbitrary_term.name
            atd_row.set('class', 'end-of-premises')
            yield atd_row

        for i,prem in enumerate(self.prems or ([None] if self.arbitrary_term is None else [])):
            row = _row(prem)

            if not self.prems or i == len(self.prems) - 1:
                row.set('class', 'end-of-premises')
            yield row

        for line in self.lines:
            if isinstance(line, Proof):
                yield from line._to_rows()
            else:
                yield _row(line)

    def to_html(self) -> str:
        if self.level > 1:
            raise ValueError('Only top-level proofs can be converted to HTML directly.')

        table = etree.Element('table', {'class': 'proof'})

        for row in self._to_rows():
            table.append(row)

        return etree.tostring(table, encoding='unicode')

    def get_line(self, num: int) -> tuple[Proof, ProofLine] | None:
        if num < self.start or num > self.end:
            if not self.parent:
                return None
            return self.parent.get_line(num)

        for line in self.prems + self.lines:
            if isinstance(line, Proof):
                if line.start <= num <= line.end:
                    return line.get_line(num)
            elif line.num == num:
                return self, line

        return None

    def invalid_arbitrary_terms(self, line: ProofLine) -> set[SymbolicTerm]:
        in_scope_terms = set[SymbolicTerm]()
        proof: Proof | None = self
        while proof is not None:
            if proof.arbitrary_term is not None:
                in_scope_terms.add(proof.arbitrary_term)
            proof = proof.parent

        terms_in_line = { term for term in extract_symbolic_terms(line.expr) if term.is_arbitrary }
        return terms_in_line - in_scope_terms

    def check(self) -> None:
        if self.arbitrary_term is not None and self.prems:
            raise ProofError(f'Arbitrary term {self.arbitrary_term} cannot be defined in a proof with premises (line {self.start})')

        if self.level > 1 and not (len(self.prems) == 1 and self.arbitrary_term is None or (len(self.prems) == 0 and self.arbitrary_term is not None)):
            raise ProofError(f'Subproofs must have exactly one premise (line {self.start})')

        for prem in self.prems:
            self._check_line(prem, expect_premise=True)

        for line in self.lines:
            if isinstance(line, Proof):
                line.check()
            else:
                self._check_line(line, expect_premise=False)

    def _check_line(self, line: ProofLine, expect_premise: bool) -> None:
        rule = find_rule(line.justification)
        if rule is None:
            raise ProofError(f'Line {line.num}: Unknown justification: {line.justification!r}')

        if expect_premise:
            if not isinstance(rule, PremiseRule):
                raise ProofError(f'Line {line.num}: Expected a premise justification, but got {line.justification!r}')
            if self.level > 1 and isinstance(rule, Premise):
                raise ProofError(f'Line {line.num}: Premises cannot be used in subproofs (line {line.num})')
            if self.level == 1 and not isinstance(rule, Premise):
                raise ProofError(f'Non-premise statement found in premise section of proof (line {line.num}). Did you forget to separate the premises?')
            return
        else:
            if isinstance(rule, PremiseRule):
                raise ProofError(f'Line {line.num}: Premise justifications are not allowed outside of the premises section (line {line.num})')

        if invalid_terms := self.invalid_arbitrary_terms(line):
            invalid_terms_str = ', '.join(term.name for term in invalid_terms)
            raise ProofError(f'Line {line.num}: The following arbitrary terms are not in scope: {invalid_terms_str} (referenced in line {line.num}: {line.justification})')

        def get_line_or_die(num: int) -> tuple[Proof, ProofLine]:
            line_info = self.get_line(num)
            if line_info is None:
                raise ProofError(f'Line {num} not found (referenced on line {line.num}: {line.justification})')
            return line_info

        if isinstance(rule, InferenceRule):
            prems = list[Expr]()
            for num in rule.prem_lines:
                prem_proof, prem_line = get_line_or_die(num)
                if prem_proof.level > self.level:
                    raise ProofError(f'Line {num} is not accessible from line {line.num} ({line.justification})')
                prems.append(prem_line.expr)
            logging.debug(f'Checking line {line.num}: {line.expr.render()} with premises {prems} against rule {rule.__class__.__name__}')

            try:
                rule.check(line.expr, prems)
            except ProofError as e:
                raise ProofError(f'Line {line.num}: {e}')

        elif isinstance(rule, SubproofRule):
            start_proof, start_line = get_line_or_die(rule.start)
            end_proof, end_line = get_line_or_die(rule.end)
            if start_proof is not end_proof:
                raise ProofError(f'Lines {rule.start} and {rule.end} are not in the same subproof (referenced on line {line.num}: {line.justification})')
            if rule.start != start_proof.start:
                raise ProofError(f'Line {rule.start} is not the start of a subproof (referenced on line {line.num}: {line.justification})')
            if rule.end != end_proof.end:
                raise ProofError(f'Line {rule.end} is not the end of a subproof (referenced on line {line.num}: {line.justification})')

            try:
                rule.check(line.expr, start_proof)
            except ProofError as e:
                raise ProofError(f'Line {line.num}: {e}')

        else:
            raise NotImplementedError(f'Unknown rule type: {type(rule)}')
