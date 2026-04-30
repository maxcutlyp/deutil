import typing as t

from pathlib import Path
import logging
import argparse

from .rules import print_rules_help
from .convert import convert
from .countermodel import repl as cm_repl


# Source - https://stackoverflow.com/a/48051233
# Posted by Naitree, modified by community. See post 'Timeline' for change history
# Retrieved 2026-04-30, License - CC BY-SA 3.0

class NoSubparsersMetavarFormatter(argparse.HelpFormatter):
    def _format_action(self, action: argparse.Action) -> str:
        result = super()._format_action(action)
        if isinstance(action, argparse._SubParsersAction):
            # fix indentation on first line
            return "%*s%s" % (self._current_indent, "", result.lstrip())
        return result

    def _format_action_invocation(self, action: argparse.Action) -> str:
        if isinstance(action, argparse._SubParsersAction):
            # remove metavar and help line
            return ""
        return super()._format_action_invocation(action)

    def _iter_indented_subactions(self, action: argparse.Action) -> t.Generator[argparse.Action, None, None]:
        if isinstance(action, argparse._SubParsersAction):
            try:
                get_subactions = action._get_subactions
            except AttributeError:
                pass
            else:
                # remove indentation
                yield from get_subactions()
        else:
            yield from super()._iter_indented_subactions(action)

parser = argparse.ArgumentParser(description='Tools for working with DeLancy-style proofs.', formatter_class=NoSubparsersMetavarFormatter)
parser.add_argument('--help-rules', action='store_true', help='Show the rules that are supported in the proofs and exit.')
subparsers = parser.add_subparsers(title='subcommands', required=True, metavar='SUBCOMMAND')
parser.add_argument('--debug', action='store_true', help='Enable debug logging.')

convert_parser = subparsers.add_parser('convert', help='Convert a Markdown file with DeLancy-style proofs to PDF')
convert_parser.add_argument('input', help='The input Markdown file.')
convert_parser.add_argument('output', nargs='?', help='The output PDF file. If not provided, the output file will have the same name as the input file but with a .pdf extension.')
convert_parser.add_argument('--check', action=argparse.BooleanOptionalAction, default=True, help='Whether to check the proofs for correctness. Default is True.')
convert_parser.add_argument('--pdf', action=argparse.BooleanOptionalAction, default=True, help='Whether to write the output PDF file. Default is True.')
convert_parser.add_argument('--html', action=argparse.BooleanOptionalAction, default=False, help='Whether to write the intermediate HTML file. Default is False.')

countermodel_parser = subparsers.add_parser('countermodel', help='Find countermodels for a given formula. For PL, this is done with a truth tables; for FOL, a best-effort (though necessarily incomplete) search is performed.')

logging.basicConfig(level=logging.DEBUG if parser.parse_args().debug else logging.INFO)

def main_convert(args: argparse.Namespace) -> int:
    if not args.input:
        print('Error: No input file provided.\n')
        convert_parser.print_help()
        return 1

    input_file = Path(args.input)
    output_file = Path(args.output) if args.output else input_file.with_suffix('.pdf')

    convert(
        input_file,
        output_file,
        check=args.check,
        write_pdf=args.pdf,
        write_html=args.html,
    )
    return 0
convert_parser.set_defaults(func=main_convert)

def main_countermodel(args: argparse.Namespace) -> int:
    return cm_repl()
countermodel_parser.set_defaults(func=main_countermodel)

def main() -> int:
    args = parser.parse_args()

    if args.help_rules:
        print_rules_help()
        return 0

    return t.cast(t.Callable[[argparse.Namespace], int], args.func)(args)

if __name__ == "__main__":
    raise SystemExit(main())
