from __future__ import annotations

import struct
from pathlib import Path
from .models import ArrangementPlan, Note


def _vlq(value: int) -> bytes:
    out = [value & 0x7F]; value >>= 7
    while value:
        out.append((value & 0x7F) | 0x80); value >>= 7
    return bytes(reversed(out))


def write_midi(plan: ArrangementPlan, path: str | Path) -> Path:
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    tracks = []
    for channel, track in enumerate(plan.tracks[:15]):
        events = []
        for n in track.notes:
            start = round(n.start * 480); end = round((n.start+n.duration)*480)
            events += [(start, 1, bytes([0x90 | channel, n.pitch, n.velocity])), (end, 0, bytes([0x80 | channel, n.pitch, 0]))]
        events.sort(key=lambda e: (e[0], e[1]))
        data = bytearray(); previous = 0
        for tick, _, msg in events:
            data += _vlq(tick - previous) + msg; previous = tick
        data += b"\x00\xff\x2f\x00"
        name = track.name.encode()[:24]
        payload = b"\x00\xff\x03" + bytes([len(name)]) + name + bytes(data)
        tracks.append(b"MTrk" + struct.pack(">I", len(payload)) + payload)
    header = b"MThd" + struct.pack(">IHHH", 6, 1, len(tracks), 480)
    path.write_bytes(header + b"".join(tracks)); return path
