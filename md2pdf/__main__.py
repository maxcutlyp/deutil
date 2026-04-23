from __future__ import annotations
import sys
import markdown
import typing as t

from bs4 import BeautifulSoup
from markdown.preprocessors import Preprocessor
from markdown.postprocessors import Postprocessor
from markdown.treeprocessors import Treeprocessor
from pathlib import Path
from weasyprint import HTML  # type:ignore[import-untyped]
import logging

from .proof import Proof
from .rules import ProofError

logging.basicConfig()

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

.arbitrary-term {
    border: 1px solid currentColor;
    padding: 0.25em 0.5em;
    margin: 0.25em;
    display: inline-block;
}
'''

class StylePostprocessor(Postprocessor):
    def run(self, text: str) -> str:
        return '<style>' + CSS + '</style>' + text

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
                try:
                    proof.check()
                except ProofError as e:
                    raise ProofError(f'Error checking proof starting on line {real_i + 1}: {e}')
                html = proof.to_html()
                lines[i] = html
                for _ in range(len(proof_lines) - 1):
                    lines.pop(i + 1)
                    real_i += 1

            i += 1
            real_i += 1

        return lines

class HeadingFixerPostProcessor(Postprocessor):
    ''' If a heading is immediately before a proof, wrap them both in a div with `page-break-inside: avoid` to prevent them from being separated across pages. '''

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
    except (SyntaxError, ProofError) as e:
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
