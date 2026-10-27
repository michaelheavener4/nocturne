from __future__ import annotations

import re
import struct
from dataclasses import dataclass


class InvalidMidi(AssertionError):
    pass


NOTE_PITCH_CLASS = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}
SCALE_INTERVALS = {
    "major": frozenset({0, 2, 4, 5, 7, 9, 11}),
    "minor": frozenset({0, 2, 3, 5, 7, 8, 10}),
}
_KEY_RE = re.compile(
    r"(?<![A-Za-z])([A-Ga-g])([#♯b♭]?)\s*(major|minor|maj|min)\b",
    re.IGNORECASE,
)
_DRUM_TRACK_RE = re.compile(r"\bdrum", re.IGNORECASE)
_GENERAL_MIDI_DRUM_CHANNEL = 9


@dataclass
class MidiTrack:
    name: str | None
    notes: list[tuple[int, int]]


def parse_prompt_key(prompt: str) -> tuple[int, str] | None:
    """Return ``(tonic_pitch_class, mode)`` for the first key named in a prompt."""
    match = _KEY_RE.search(prompt)
    if not match:
        return None
    name, accidental, mode = match.groups()
    tonic = NOTE_PITCH_CLASS[name.upper()]
    if accidental in ("#", "♯"):
        tonic += 1
    elif accidental in ("b", "♭"):
        tonic -= 1
    return tonic % 12, "major" if mode.lower().startswith("maj") else "minor"


def expected_scale_pitch_classes(prompt: str) -> frozenset[int]:
    """Return the pitch classes of the scale named by the prompt's key."""
    parsed = parse_prompt_key(prompt)
    if parsed is None:
        raise ValueError(f"prompt does not name a key: {prompt!r}")
    tonic, mode = parsed
    return frozenset((tonic + interval) % 12 for interval in SCALE_INTERVALS[mode])


def _read_vlq(data: bytes, offset: int) -> tuple[int, int]:
    value = 0
    while True:
        if offset >= len(data):
            raise InvalidMidi("truncated variable-length quantity")
        byte = data[offset]
        offset += 1
        value = (value << 7) | (byte & 0x7F)
        if not byte & 0x80:
            return value, offset


def parse_midi_tracks(data: bytes) -> list[MidiTrack]:
    """Parse the note-on events and track names out of a Standard MIDI File.

    This is deliberately a small, local reader: the verification harness must
    not depend on an external MIDI library to check what the project wrote.
    """
    assert_valid_midi(data)
    _, ntrks, _ = struct.unpack(">HHH", data[8:14])
    offset = 14
    tracks: list[MidiTrack] = []
    for _ in range(ntrks):
        chunk_length = struct.unpack(">I", data[offset + 4:offset + 8])[0]
        start = offset + 8
        end = start + chunk_length
        payload = data[start:end]
        cursor = 0
        running_status: int | None = None
        name: str | None = None
        notes: list[tuple[int, int]] = []
        while cursor < len(payload):
            _, cursor = _read_vlq(payload, cursor)
            if cursor >= len(payload):
                raise InvalidMidi("truncated event status")
            status = payload[cursor]
            if status < 0x80:
                if running_status is None:
                    raise InvalidMidi("running status without a prior status byte")
                status = running_status
            else:
                cursor += 1
                if status < 0xF0:
                    running_status = status

            if status == 0xFF:
                if cursor >= len(payload):
                    raise InvalidMidi("truncated meta event")
                meta_type = payload[cursor]
                cursor += 1
                length, cursor = _read_vlq(payload, cursor)
                meta = payload[cursor:cursor + length]
                if len(meta) != length:
                    raise InvalidMidi("truncated meta event payload")
                cursor += length
                if meta_type == 0x03:
                    name = meta.decode("latin-1", errors="replace")
                if meta_type == 0x2F:
                    break
            elif status in (0xF0, 0xF7):
                length, cursor = _read_vlq(payload, cursor)
                cursor += length
                if cursor > len(payload):
                    raise InvalidMidi("truncated system-exclusive event")
            else:
                high = status & 0xF0
                channel = status & 0x0F
                data_length = 1 if high in (0xC0, 0xD0) else 2
                if cursor + data_length > len(payload):
                    raise InvalidMidi("truncated channel event")
                first = payload[cursor]
                if high == 0x90 and data_length == 2 and payload[cursor + 1] > 0:
                    notes.append((channel, first))
                cursor += data_length
        tracks.append(MidiTrack(name=name, notes=notes))
        offset = end
    return tracks


def pitched_pitch_classes(data: bytes) -> set[int]:
    """Pitch classes of every note-on event except the drum channel/track."""
    pitch_classes: set[int] = set()
    for track in parse_midi_tracks(data):
        if track.name and _DRUM_TRACK_RE.search(track.name):
            continue
        for channel, pitch in track.notes:
            if channel == _GENERAL_MIDI_DRUM_CHANNEL:
                continue
            pitch_classes.add(pitch % 12)
    return pitch_classes


def assert_valid_midi(data: bytes) -> None:
    """Validate the MIDI header and every MTrk chunk, then return None.

    This intentionally checks structure only: the harness cares that each run
    produces a real, well-formed Standard MIDI File, not that a particular
    library agrees with our hand-rolled writer.
    """
    if len(data) < 14:
        raise InvalidMidi(f"file is too short for a MIDI header: {len(data)} bytes")
    if data[0:4] != b"MThd":
        raise InvalidMidi(f"missing MThd header: {data[0:4]!r}")
    header_length = struct.unpack(">I", data[4:8])[0]
    if header_length != 6:
        raise InvalidMidi(f"MThd length is {header_length}, expected 6")
    fmt, ntrks, division = struct.unpack(">HHH", data[8:14])
    if fmt not in (0, 1, 2):
        raise InvalidMidi(f"unknown MIDI format {fmt}")
    if ntrks < 1:
        raise InvalidMidi("header declares zero tracks")
    if division & 0x8000:
        raise InvalidMidi("expected ticks-per-quarter-note division (SMPTE not used by composer)")

    offset = 14
    for index in range(ntrks):
        if offset + 8 > len(data):
            raise InvalidMidi(f"track {index}: truncated chunk header at byte {offset}")
        chunk_type = data[offset:offset + 4]
        chunk_length = struct.unpack(">I", data[offset + 4:offset + 8])[0]
        if chunk_type != b"MTrk":
            raise InvalidMidi(f"track {index}: expected MTrk, found {chunk_type!r}")
        start = offset + 8
        end = start + chunk_length
        if end > len(data):
            raise InvalidMidi(
                f"track {index}: chunk length {chunk_length} exceeds remaining file bytes"
            )
        payload = data[start:end]
        if len(payload) < 4 or payload[-4:] != b"\x00\xff\x2f\x00":
            raise InvalidMidi(f"track {index}: does not end with end-of-track meta event")
        offset = end

    if offset != len(data):
        raise InvalidMidi(f"{len(data) - offset} trailing bytes after last declared track")
