from __future__ import annotations

from abc import ABC, abstractmethod
from frozendict import frozendict
from enum import Enum
from itertools import product
from pathlib import Path
import builtins
import re
import readline
import atexit
import typing as t
import logging
import sys
import os

from .expr import (
    Atom,
    And,
    Or,
    Imp,
    Bij,
    Not,
    Expr,
    extract_atoms,
    ExpressionParser,
)

type TTRowAssignment = frozendict[Atom, bool]
type TTRowResult = t.OrderedDict[Expr, bool]
type TruthTable = t.Mapping[TTRowAssignment, TTRowResult]

def make_truth_table(*exprs: Expr) -> TruthTable:
    atoms = set.union(*(extract_atoms(expr) for expr in exprs))
    truth_table = dict[frozendict[Atom, bool], t.OrderedDict[Expr, bool]]()
    for assignment in product([True, False], repeat=len(atoms)):
        assignment_dict = frozendict(zip(atoms, assignment))
        truth_table[assignment_dict] = t.OrderedDict((
            (expr, expr.evaluate(assignment_dict))
            for expr in exprs
        ))
    return truth_table

def is_counterexample(result: TTRowResult) -> bool:
    *prems, conc = result.values()
    if not prems:
        return False
    return all(prems) and not conc

def render_truth_table(truth_table: TruthTable) -> str:
    esc_seq_regex = re.compile('\x1b' + r'\[(\d+(;\d+)*)?[a-zA-Z]')
    def screenlen(x: str) -> int:
        return len(re.sub(esc_seq_regex, '', x))

    def s(value: bool, red: bool = False) -> str:
        val = 'T' if value else 'F'
        if red:
            return f'\033[31m{val}\033[39m'
        return val

    def centered(x: str, width: int) -> str:
        padding = width - screenlen(x)
        left_pad = padding // 2
        right_pad = padding - left_pad
        return ' ' * left_pad + x + ' ' * right_pad

    UNDERLINE_START = '\033[4m'
    UNDERLINE_END = '\033[24m'

    atoms = sorted(next(iter(truth_table.keys())).keys(), key=lambda atom: atom.name)
    exprs = next(iter(truth_table.values())).keys()
    header = ''.join([
        UNDERLINE_START,
        ' ',
        ' | '.join(atom.name for atom in atoms),
        ' | ',
        ' | '.join(expr.render() for expr in exprs),
        ' |',
        UNDERLINE_END,
    ])

    lines = [header]
    for assignment, results in sorted(
        truth_table.items(),
        key=lambda item: tuple(item[0][atom] for atom in atoms),
        reverse=True,
    ):
        red = is_counterexample(results)
        line = ''.join([
            ' ',
            ' | '.join(s(assignment[atom], red=red) for atom in atoms),
            ' | ',
            ' | '.join(centered(s(results[expr], red=red), len(expr.render())) for expr in exprs),
            ' |',
        ])
        lines.append(line)

    return '\n'.join(lines).replace('|', '│')

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
        truth_table = make_truth_table(*exprs)
    except SyntaxError as e:
        print("Syntax error:", e)
        return

    rendered = render_truth_table(truth_table)
    print(rendered)

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

def truth_tables_repl() -> int:
    try:
        readline.read_init_file()
    except FileNotFoundError:
        pass

    load_history()

    print('Entered truth table repl. Press Ctrl+D to exit.')

    try:
        while True:
            try:
                loop()
            except KeyboardInterrupt:
                print()
    except EOFError:
        print()
    return 0

