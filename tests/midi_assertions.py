from __future__ import annotations

import struct


class InvalidMidi(AssertionError):
    pass


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
