from __future__ import annotations
import re
import typing as t
import xml.etree.ElementTree as etree
import logging

from .expr import (
    Expr,
    ExpressionParser,
)

from .rules import (
    find_rule,
    ProofError,
    SubproofRule,
)

def replace_symbols(text: str) -> str:
    text = text.replace('<->', '↔')
    text = text.replace('->', '→')
    text = text.replace('^', '∧')
    text = text.replace('v', '∨')
    text = text.replace('~', '¬')
    return text

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

    def __init__(
        self,
        prems: list[ProofLine],
        lines: list[ProofLine | Proof],
        start: int,
        end: int,
        level: int,
    ):
        self.prems = prems
        self.lines = lines
        self.start = start
        self.end = end
        self.level = level
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

        i = 0
        while i < len(rawlines):
            line = rawlines[i].strip()
            i += 1
            if not line:
                continue
            if not line.startswith('|'):
                continue

            if m := re.match(rf'^{r'\|\s*' * level}', line):
                trimmed = line[m.end():]
                if trimmed.startswith('|'):
                    subproof, skip = cls._from_markdown(rawlines[i-1:], level + 1)
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

                curr.append(ProofLine(int(num), expr, justification))
                continue

            raise SyntaxError(f'Invalid proof line on line {i+1}: {line}')

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
                content_cell.text = replace_symbols(content_cell.text)

                just_cell.text = line.justification

            return row

        for i,prem in enumerate(self.prems or [None]):
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

    def check(self) -> None:
        for line in self.prems + self.lines:
            if isinstance(line, Proof):
                line.check()
            else:
                rule = find_rule(line.justification)
                if rule is None:
                    raise ProofError(f'Line {line.num}: Unknown justification: {line.justification!r}')

                prems = list[tuple[Proof, ProofLine]]()
                for num in rule.prem_lines:
                    prem_proof_and_line = self.get_line(num)
                    if prem_proof_and_line is None:
                        raise ProofError(f'Line {num} not found (referenced on line {line.num}: {line.justification})')
                    prem_proof, prem_line = prem_proof_and_line
                    if not isinstance(rule, SubproofRule) and prem_proof.level > self.level:
                        raise ProofError(f'Line {num} is not accessible from line {line.num} ({line.justification})')
                    prems.append(prem_proof_and_line)

                logging.debug(f'Checking line {line.num}: {line.expr.render()} with premises {[l.expr.render() for _,l in prems]} against rule {rule.__class__.__name__}')

                if isinstance(rule, SubproofRule):
                    try:
                        startproof, startline = prems[0]
                        endproof, endline = prems[-1]
                    except IndexError:
                        raise ProofError(f'Rule {rule.__class__.__name__} requires at least one premise line (referenced on line {line.num}: {line.justification})')

                    if startproof is not endproof or startline.num != startproof.start or endline.num != startproof.end:
                        raise ProofError(f'Lines {startline.num}-{endline.num} do not form a valid subproof (referenced on line {line.num}: {line.justification})')

                try:
                    rule.check(line.expr, [l.expr for _,l in prems])
                except ProofError as e:
                    raise ProofError(f'Line {line.num}: {e}')

