import atexit
import os
from pathlib import Path
import readline
import typing as t

from .expr import (
    Expr,
    ExpressionParser,
    is_fol,
)

from .fol_cm import find_cm as find_cm_fol
from .truthtables import find_cm as find_cm_pl

def loop() -> None:
    expr_strs = input("> ").split(',')
    exprs = list[Expr]()
    for expr_str in expr_strs:
        parser = ExpressionParser(expr_str, raise_on_extra_tokens=True)
        try:
            exprs.append(parser.parse())
        except SyntaxError as e:
            print("Syntax error:", e)
            return

    try:
        *prems, conc = exprs
    except ValueError:
        print('Error: No conclusion provided. Please provide at least one expression, where the last expression is the conclusion and the rest are premises.')
        return

    print()
    print('Argument:')
    for i,prem in enumerate(prems):
        print(f'  {prem}')
    print(f'  ⊢ {conc}')
    print()

    if any(is_fol(expr) for expr in exprs):
        find_cm_fol(prems, conc)
    else:
        find_cm_pl(prems, conc)

def get_history_file() -> Path:
    app_name = 'deutil'
    if os.name == 'nt':
        base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    else:
        base = Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local" / "state"))
    return base / app_name / "history"

def load_history() -> None:
    history_file = get_history_file()
    try:
        readline.read_history_file(history_file)
    except FileNotFoundError:
        history_file.parent.mkdir(parents=True, exist_ok=True)
        history_file.touch(exist_ok=True)
    atexit.register(readline.write_history_file, history_file)

def repl() -> int:
    try:
        readline.read_init_file()
    except FileNotFoundError:
        pass

    load_history()

    print('Entered countermodel repl. Press Ctrl+D to exit.')

    try:
        while True:
            try:
                loop()
            except KeyboardInterrupt:
                print()
    except EOFError:
        print()
    return 0

