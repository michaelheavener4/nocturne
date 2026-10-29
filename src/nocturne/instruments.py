"""Ableton instrument names and zero-based General MIDI scratch programs."""

INSTRUMENT_PROGRAMS: dict[str, tuple[int, bool]] = {
    "Ableton Core Kit": (0, True), "Electronic Kit": (24, True),
    "TR-808 Kit": (25, True), "Power Kit": (16, True), "Brush Kit": (40, True),
    "Operator": (38, False), "Analog Bass": (39, False),
    "Fingered Bass": (33, False), "Fretless Bass": (35, False),
    "Wavetable": (89, False), "Strings": (48, False),
    "Electric Piano": (5, False), "Organ": (16, False), "Choir Pad": (91, False),
    "Operator Lead": (81, False), "Analog Lead": (80, False),
    "Grand Piano": (0, False), "Music Box": (10, False),
    "Flute": (73, False), "Wavetable Lead": (88, False),
}

PALETTES: dict[str, list[str]] = {
    "drums": ["Ableton Core Kit", "Electronic Kit", "TR-808 Kit", "Power Kit", "Brush Kit"],
    "bass": ["Operator", "Analog Bass", "Fingered Bass", "Fretless Bass"],
    "harmony": ["Wavetable", "Strings", "Electric Piano", "Organ", "Choir Pad"],
    "melody": ["Operator Lead", "Analog Lead", "Grand Piano", "Electric Piano", "Music Box", "Flute", "Wavetable Lead"],
}


def lookup_instrument(name: str, role: str) -> tuple[int, bool]:
    """Resolve legacy shared names by role; unknown instruments use piano."""
    if role == "melody":
        name = {"Operator": "Operator Lead", "Wavetable": "Wavetable Lead"}.get(name, name)
    return INSTRUMENT_PROGRAMS.get(name, (0, False))
