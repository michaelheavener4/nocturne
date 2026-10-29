"""Build A7 corrections, including executable reproductions of old mistakes."""
from __future__ import annotations

import ast
import hashlib
import importlib.util
from pathlib import Path

import pytest

from nocturne import cli, song
from nocturne.arrangement import ArrangementPlanner
from nocturne.intent import IntentInterpreter
from nocturne.midi import write_midi

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('check_contracts', ROOT / 'tools/check_contracts.py')
guards = importlib.util.module_from_spec(spec)
spec.loader.exec_module(guards)


def test_shared_boundaries():
    guards.main()


@pytest.mark.parametrize('old_shape, message', [
    ('sub.add_parser("song")\nsub.add_parser("song")', 'duplicate CLI'),
    ('def _fallback_repetition_report(plan):\n return {}', 'canonical analysis import'),
])
def test_cli_guard_rejects_old_shapes(old_shape, message):
    with pytest.raises(ValueError, match=message):
        guards.check_cli(old_shape)


def test_song_guard_rejects_old_fallback():
    old = '''def plan_song(brief, form=None, groove=None):
    planner = ArrangementPlanner()
    if hasattr(planner, "plan_song"):
        return planner.plan_song(brief)
    return fallback_song(brief)
'''
    with pytest.raises(ValueError, match='delegate directly'):
        guards.check_song(old)


def _form_choices(source):
    tree = ast.parse(source)
    return next(k.value for n in ast.walk(tree) if isinstance(n, ast.Call)
                and isinstance(n.func, ast.Attribute) and n.func.attr == 'add_argument'
                and n.args and isinstance(n.args[0], ast.Constant) and n.args[0].value == '--form'
                for k in n.keywords if k.arg == 'choices')


def _assert_shared_forms(source):
    node = _form_choices(source)
    assert isinstance(node, ast.Name) and node.id == 'SONG_FORMS', 'CLI form list drift'


def test_form_registry_and_old_shape():
    source = Path(cli.__file__).read_text()
    _assert_shared_forms(source)
    with pytest.raises(AssertionError, match='form list drift'):
        _assert_shared_forms(source.replace('choices=SONG_FORMS', 'choices=("edm", "club", "pop")'))
    assert cli.SONG_FORMS is song.SONG_FORMS


def _notes(plan, role):
    return [n.model_dump() for t in plan.tracks if t.role == role for n in t.notes]


def _assert_effect(before, after, role):
    assert _notes(before, role) != _notes(after, role), f'cosmetic {role} change'


@pytest.mark.parametrize('change,role', [('key', 'harmony'), ('feedback', 'bass')])
def test_input_reaches_notes_and_rejects_metadata_only_fixture(change, role):
    interpreter = IntentInterpreter()
    brief = interpreter.interpret('dark and tense, D minor, 92 bpm')
    planner = ArrangementPlanner()
    before = planner.plan(brief)
    revised = brief.model_copy(deep=True)
    if change == 'key':
        revised.musical_constraints['key'] = 'C major'
    else:
        revised.intent += ' [feedback: make the bass less busy and let the notes ring]'
    _assert_effect(before, planner.plan(revised), role)
    # Findings 001/002: labels and rationale change while seeds stay fixed.
    old = before.model_copy(update={'key': 'C major', 'rationale': ['revised as requested']})
    with pytest.raises(AssertionError, match='cosmetic'):
        _assert_effect(before, old, role)


@pytest.mark.parametrize('form,digest', [
    (None, '2645c4f1436bd771b579aad3ed71b06b'),
    ('edm', '2645c4f1436bd771b579aad3ed71b06b'),
    ('club', '13363b9c6ba220b1562c939a08c6005f'),
    ('pop', '7aa3def65cb55c96f203b11283829b38'),
    ('pop84', 'b8a148690241d434deb662826f7f6008'),
])
def test_prompt_steered_song_bytes(form, digest, tmp_path):
    # Stream 75A song identity: seeded progression, motif, bass and drums.
    brief = IntentInterpreter().interpret('dark and tense EDM track, D minor, 92 bpm')
    plan = song.plan_song(brief, form=form)
    assert hashlib.md5(write_midi(plan, tmp_path / 'song.mid').read_bytes()).hexdigest() == digest


def test_cli_accepts_every_shared_form(monkeypatch):
    seen = []
    monkeypatch.setattr(cli, 'song_command', lambda args: seen.append(args.form) or 0)
    for form in song.SONG_FORMS:
        assert cli.main(['song', '--prompt', 'dark and tense', '--form', form]) == 0
    assert tuple(seen) == song.SONG_FORMS


def test_analysis_guard_rejects_parallel_implementation():
    old = '''from .analysis import repetition_report

def _fallback_repetition_report(plan):
    return {"repetitive_flag": False}
'''
    with pytest.raises(ValueError, match='local repetition_report'):
        guards.check_cli(old)
