# src/nocturne/songbook.py

PROGRESSIONS = {
    "minor": [
        [(1, "min"), (6, "min"), (3, "min"), (7, "min")],  # default
        [(1, "min"), (4, "min"), (5, "min"), (7, "min")],
        [(1, "min"), (2, "min"), (5, "min"), (7, "min")],
        [(1, "min"), (6, "min"), (4, "min"), (7, "min")]
    ],
    "major": [
        [(1, "maj"), (5, "maj"), (6, "min"), (4, "maj")],  # default
        [(1, "maj"), (2, "maj"), (4, "maj"), (5, "maj")],
        [(1, "maj"), (3, "maj"), (6, "min"), (7, "maj")],
        [(1, "maj"), (5, "maj"), (3, "maj"), (7, "maj")]
    ]
}

VOICINGS = {
    "maj": [
        [0, 4, 7, 12],  # root, third, fifth, octave
        [0, 3, 7, 10]   # root, second, fifth, seventh
    ],
    "min": [
        [0, 3, 7, 12],  # root, third, fifth, octave
        [0, 4, 7, 11]   # root, second, fifth, sixth
    ],
    "dim": [
        [0, 3, 6, 12],  # root, third, fifth, octave
        [0, 4, 6, 10]   # root, second, fifth, seventh
    ]
}

FILL_PATTERNS = [
    [
        (0, 35, 100), (4, 38, 100), (8, 42, 100), (12, 46, 100),
        (14, 42, 127)
    ],
    [
        (0, 36, 100), (4, 38, 100), (8, 40, 100), (12, 42, 100),
        (14, 40, 127)
    ],
    [
        (0, 35, 100), (4, 37, 100), (8, 39, 100), (12, 41, 100),
        (14, 39, 127)
    ],
    [
        (0, 36, 100), (4, 38, 100), (8, 40, 100), (12, 42, 100),
        (14, 40, 127)
    ]
]

RISER = {
    "density": [0, 1, 2, 3, 4, 5, 6, 7],
    "register": [60, 62, 64, 66, 68, 70, 72, 74]
}

SECTION_ENERGY = {
    "edm": {
        "intro": 0.45,
        "verse": 0.55,
        "build": 0.75,
        "drop": 0.95,
        "chorus": 0.95,
        "pre-chorus": 0.65,
        "breakdown": 0.55,
        "bridge": 0.65,
        "outro": 0.45
    },
    "pop": {
        "intro": 0.45,
        "verse": 0.55,
        "build": 0.75,
        "drop": 0.95,
        "chorus": 0.95,
        "pre-chorus": 0.65,
        "breakdown": 0.55,
        "bridge": 0.65,
        "outro": 0.45
    }
}

def progression(mode, index=0):
    return PROGRESSIONS.get(mode, [])[index]

def voicing(quality, index=0):
    return VOICINGS.get(quality, [])[index]

def fill(index=0):
    return FILL_PATTERNS[index]

def section_energy(form, role):
    return SECTION_ENERGY.get(form, {}).get(role, 0.5)
