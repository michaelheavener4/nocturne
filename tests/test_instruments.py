"""Instrument identity must reach MIDI without changing the musical events."""
import struct

import pytest

from midi_assertions import _read_vlq
from nocturne.arrangement import ArrangementPlanner
from nocturne.instruments import INSTRUMENT_PROGRAMS, PALETTES, lookup_instrument
from nocturne.intent import IntentInterpreter
from nocturne.midi import write_midi
from nocturne.models import ArrangementPlan, Note, TrackPlan
from test_prompt_steering_battery import PROMPTS, plan_for


def channel_events(data):
    offset = 14
    tracks = []
    while offset < len(data):
        length = struct.unpack('>I', data[offset + 4:offset + 8])[0]
        payload = data[offset + 8:offset + 8 + length]
        offset += 8 + length
        pos = tick = 0
        events = []
        while pos < len(payload):
            delta, pos = _read_vlq(payload, pos)
            tick += delta
            status = payload[pos]
            pos += 1
            if status == 0xFF:
                pos += 1
                size, pos = _read_vlq(payload, pos)
                pos += size
            else:
                size = 1 if status & 0xF0 == 0xC0 else 2
                events.append((tick, status, tuple(payload[pos:pos + size])))
                pos += size
        tracks.append(events)
    return tracks


@pytest.mark.parametrize('name,role,expected', [
    ('Operator', 'bass', (38, False)), ('Operator', 'melody', (81, False)),
    ('Wavetable', 'harmony', (89, False)), ('Wavetable', 'melody', (88, False)),
    ('Electronic Kit', 'melody', (24, True)), ('unknown', 'melody', (0, False)),
])
def test_legacy_and_unknown_names(name, role, expected):
    assert lookup_instrument(name, role) == expected


@pytest.mark.parametrize('name,expected', INSTRUMENT_PROGRAMS.items())
def test_all_programs(name, expected):
    assert lookup_instrument(name, 'bass') == expected


def test_channel_allocation_and_program_before_notes(tmp_path):
    specs = [('drums', 'unknown'), ('melody', 'TR-808 Kit')]
    specs += [('melody', 'Operator')] * 13
    plan = ArrangementPlan(title='routing', tempo=120, key='C minor', bars=1,
        tracks=[TrackPlan(name=str(i), role=role, instrument=name,
                         notes=[Note(pitch=60, start=0, duration=1, velocity=90)])
                for i, (role, name) in enumerate(specs)])
    events = channel_events(write_midi(plan, tmp_path / 'routing.mid').read_bytes())
    channels = [9, 9, *range(9), 10, 11, 12, 13]
    for track, channel, track_events in zip(plan.tracks, channels, events):
        program, _ = lookup_instrument(track.instrument, track.role)
        assert track_events == [(0, 0xC0 | channel, (program,)),
                                (0, 0x90 | channel, (60, 90)),
                                (480, 0x80 | channel, (60, 0))]


@pytest.mark.parametrize('words,instrument', [
    *((word, 'Electronic Kit') for word in ('techno', 'house', 'club', 'edm', 'rave')),
    ('trap', 'TR-808 Kit'),
    *((word, 'Brush Kit') for word in ('lofi', 'jazz', 'slow', 'chill')),
    *((word, 'Power Kit') for word in ('punk', 'fast', 'driving')),
    ('piano', 'Grand Piano'),
    *((word, 'Music Box') for word in ('dreamy', 'ambient', 'ethereal')),
    ('flute', 'Flute'), ('orchestral', 'Flute'),
])
def test_word_steering(words, instrument):
    role = 'drums' if INSTRUMENT_PROGRAMS[instrument][1] else 'melody'
    assert next(t.instrument for t in plan_for(words).tracks if t.role == role) == instrument


def test_battery_diversity_and_feedback_identity(tmp_path):
    plans = [plan_for(text, form) for _, text, form in PROMPTS]
    for role, minimum in [('drums', 3), ('bass', 2), ('melody', 3)]:
        assert len({t.instrument for p in plans for t in p.tracks if t.role == role}) >= minimum
    for plan in plans:
        assert all(t.instrument in PALETTES[t.role] for t in plan.tracks)
    _, text, form = PROMPTS[0]
    brief = IntentInterpreter().interpret(text)
    brief.intent += ' [feedback: piano trap]'
    revised = ArrangementPlanner().song(brief, form=form)
    assert plans[0].model_dump() == revised.model_dump()
    assert write_midi(plans[0], tmp_path / 'a.mid').read_bytes() == write_midi(
        plan_for(text, form), tmp_path / 'b.mid').read_bytes()
