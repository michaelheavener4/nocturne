"""Static boundary guards for the duplicate implementations seen in Builds 4/5.

Run directly, or through tests/test_correct_pass.py in the merge gate.
"""
from __future__ import annotations

import ast
from pathlib import Path


def check_cli(source: str) -> None:
    tree = ast.parse(source)
    commands = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            if node.func.attr == 'add_parser' and node.args and isinstance(node.args[0], ast.Constant):
                commands.append(node.args[0].value)
    if len(commands) != len(set(commands)):
        raise ValueError('duplicate CLI subcommand')
    # Integration code must import the shared analysis implementation directly.
    imports = [n for n in tree.body if isinstance(n, ast.ImportFrom) and n.module == 'analysis']
    if not any(any(a.name == 'repetition_report' for a in n.names) for n in imports):
        raise ValueError('repetition_report must use the canonical analysis import')
    if any(isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and 'repetition_report' in n.name for n in ast.walk(tree)):
        raise ValueError('local repetition_report implementation or adapter')


def check_song(source: str) -> None:
    tree = ast.parse(source)
    functions = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'plan_song']
    if len(functions) != 1:
        raise ValueError('one shared plan_song entry point required')
    body = functions[0].body
    if isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant) and isinstance(body[0].value.value, str):
        body = body[1:]
    expected = ast.parse('return ArrangementPlanner().song(brief, form=form, groove=groove)').body[0]
    if len(body) != 1 or ast.dump(body[0]) != ast.dump(expected):
        raise ValueError('plan_song must delegate directly to ArrangementPlanner.song; no fallback planner')


def main() -> None:
    root = Path(__file__).resolve().parents[1] / 'src' / 'nocturne'
    check_cli((root / 'cli.py').read_text())
    check_song((root / 'song.py').read_text())
    print('shared implementation contracts: PASS')


if __name__ == '__main__':
    main()
