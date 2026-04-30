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
    Expr,
    extract_atoms,
    ExpressionParser,
)

from .termutils import (
    screenlen,
    underline,
    red as red_text,
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
    def s(value: bool, red: bool = False) -> str:
        val = 'T' if value else 'F'
        if red:
            return red_text(val)
        return val

    def centered(x: str, width: int) -> str:
        padding = width - screenlen(x)
        left_pad = padding // 2
        right_pad = padding - left_pad
        return ' ' * left_pad + x + ' ' * right_pad

    atoms = sorted(next(iter(truth_table.keys())).keys(), key=lambda atom: atom.name)
    exprs = next(iter(truth_table.values())).keys()
    header = underline(''.join([
        ' ',
        ' | '.join(atom.name for atom in atoms),
        ' | ',
        ' | '.join(expr.render() for expr in exprs),
        ' |',
    ]))

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

def find_cm(prems: list[Expr], conc: Expr) -> None:
    try:
        truth_table = make_truth_table(*prems, conc)
    except SyntaxError as e:
        print("Syntax error:", e)
        return

    rendered = render_truth_table(truth_table)
    print(rendered)

