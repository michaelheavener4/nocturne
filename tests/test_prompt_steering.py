"""Prompt interpretation and seeded song identity contracts."""
import pytest

from nocturne.intent import IntentInterpreter
from nocturne.song import plan_song


@pytest.mark.parametrize('word,low,high', [
    *[(w, 76, 92) for w in ('lofi', 'chill', 'ballad', 'slow', 'dreamy', 'ambient', 'downtempo')],
    *[(w, 122, 132) for w in ('techno', 'house', 'club', 'dance', 'rave')],
    *[(w, 138, 150) for w in ('punk', 'fast', 'driving', 'urgent', 'intense')],
])
def test_tempo_families_and_explicit_override(word, low, high):
    interpreter = IntentInterpreter()
    constraints = interpreter.interpret(word).musical_constraints
    assert low <= constraints['tempo_bpm'] <= high
    assert interpreter.interpret(word).musical_constraints == constraints
    assert interpreter.interpret(word + ' 105 bpm').musical_constraints['tempo_bpm'] == 105


@pytest.mark.parametrize('word', ['happy', 'bright', 'sunny', 'cheerful', 'euphoric', 'uplifting', 'playful'])
def test_key_precedence(word):
    interpreter = IntentInterpreter()
    key = interpreter.interpret(word).musical_constraints['key']
    assert key in {f'{tonic} major' for tonic in ('C', 'D', 'F', 'G', 'A')}
    assert interpreter.interpret(word + ' dark').musical_constraints['key'] == 'A minor'
    assert interpreter.interpret(word + ' dark F# major').musical_constraints['key'] == 'F# major'


def test_song_feedback_preserves_seed_and_identity():
    brief = IntentInterpreter().interpret('a lighthouse keeper writes a synth pop song about missing the mainland')
    original = plan_song(brief, form='pop84')
    brief.intent += ' [feedback: more intense]'
    assert plan_song(brief, form='pop84') == original
