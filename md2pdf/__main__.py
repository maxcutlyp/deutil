from __future__ import annotations
import sys
import markdown
import xml.etree.ElementTree as etree
import re
import typing as t

from bs4 import BeautifulSoup
from markdown.preprocessors import Preprocessor
from markdown.postprocessors import Postprocessor
from markdown.treeprocessors import Treeprocessor
from pathlib import Path
from weasyprint import HTML  # type:ignore[import-untyped]
import logging

from .expr import (
    Expr,
    ExpressionParser,
)

WRITE_HTML = True

CSS = '''
table.proof {
    border-collapse: collapse;
}

table.proof td {
    padding: 0.25em 0.5em;
}

table.proof td.border-left {
    border-left: 1px solid currentColor;
}

table.proof .end-of-premises td:where(:nth-last-child(2)) {
    border-bottom: 1px solid currentColor;
}

table.proof td:not(:nth-last-child(2)) {
  width: 0;
  white-space: nowrap;
}
'''

class StylePostprocessor(Postprocessor):
    def run(self, text: str) -> str:
        return '<style>' + CSS + '</style>' + text

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

class ProofFormatter(Preprocessor):
    '''
    Formats proofs (consecutive lines starting with '|').

    Example:

| 1. ~(P ^ Q)        Premise
|-
| | 2. ~(~P v ~Q)    Assumption for Indirect Proof
| |-
| | | 3. ~P          Assumption for Indirect Proof
| | |-
| | | 4. (~P v ~Q)   Addition: 3
| | | 5. ~(~P v ~Q)  Repeat: 2
| | 6. P             Indirect Proof: 3-5
| | | 7. ~Q          Assumption for Indirect Proof
| | |-
| | | 8. (~P v ~Q)   Addition: 7
| | | 9. ~(~P v ~Q)  Repeat: 2
| | 11. Q            Indirect Proof: 7-9
| | 12. (P ^ Q)      Adjunction: 6, 11
| | 13. ~(P ^ Q)     Repeat: 1
| 14. (~P v ~Q)      Indirect Proof: 2-13
    '''

    def run(self, lines: list[str]) -> list[str]:
        def _proof(start: int) -> t.Iterable[str]:
            for line in lines[start:]:
                if line.strip().startswith('|'):
                    yield line
                else:
                    break

        i = 0
        real_i = 0
        while i < len(lines):
            if lines[i].strip().startswith('|'):
                proof_lines = list(_proof(i))
                try:
                    proof = Proof.from_markdown(proof_lines)
                except SyntaxError as e:
                    raise SyntaxError(f'Error parsing proof starting on line {real_i + 1}: {e}')
                logging.debug(proof)
                html = proof.to_html()
                lines[i] = html
                for _ in range(len(proof_lines) - 1):
                    lines.pop(i + 1)
                    real_i += 1

            i += 1
            real_i += 1

        return lines

class HeadingFixerPostProcessor(Postprocessor):
    ''' If a heading is immediately before a <proof>, wrap them both in a div with `page-break-inside: avoid` to prevent them from being separated across pages. '''

    def run(self, text: str) -> str:
        soup = BeautifulSoup(text, 'html.parser')
        for proof in soup.find_all('table', class_='proof'):
            prev = (proof.parent or proof).find_previous_sibling()
            if prev and prev.name in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6']:
                wrapper = soup.new_tag('div')
                wrapper['style'] = 'page-break-inside: avoid;'
                prev.wrap(wrapper)
                proof.wrap(wrapper)
            else:
                proof['style'] = 'page-break-inside: avoid;'
        return str(soup)

class ProofExtension(markdown.Extension):
    def extendMarkdown(self, md: markdown.Markdown) -> None:
        md.preprocessors.register(ProofFormatter(md), 'proof_formatter', 20)
        md.postprocessors.register(StylePostprocessor(md), 'style_postprocessor', 25)
        md.postprocessors.register(HeadingFixerPostProcessor(md), 'heading_fixer_postprocessor', 15)

def convert(input_file: Path, output_file: Path) -> None:
    with input_file.open() as f:
        md_content = f.read()

    try:
        html_content = markdown.markdown(md_content, extensions=[ProofExtension()])
    except SyntaxError as e:
        logging.error(e)
        sys.exit(1)

    if WRITE_HTML:
        output_file.with_suffix('.html').write_text(html_content)
    HTML(string=html_content).write_pdf(output_file)

def usage() -> None:
    print(f'Usage: {sys.argv[0]} <input.md> <output.pdf>')

def main() -> int:
    if len(sys.argv) > 3 or len(sys.argv) < 2:
        usage()
        return 1

    input_file = Path(sys.argv[1])
    if len(sys.argv) > 2:
        output_file = Path(sys.argv[2])
    else:
        output_file = input_file.with_suffix('.pdf')

    convert(input_file, output_file)
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
