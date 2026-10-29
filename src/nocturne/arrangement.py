from __future__ import annotations

from .models import ArrangementPlan, CreativeBrief, Note, TrackPlan
from .intent import parse_feedback
from .grooves import GM_PERCUSSION, GROOVE_PRESETS, ghost_velocity
import re
import hashlib
import json
import random


# Labelled heuristics, NOT research-measured defaults; underlying corpus:
# 1955-1991 rock/pop. Register direction is implemented in scale degrees.
CONTRAST_HEURISTICS = {"chorus_velocity_factor": 1.10,
                       "chorus_register_semitones": 2, "verse_velocity_factor": 0.95}


def _repeat(notes: list[Note], bars: int = 8) -> list[Note]:
    return [n.model_copy(update={"start": n.start + bar * 4}) for bar in range(bars) for n in notes]


def _scale(key: str) -> tuple[int, tuple[int, ...]]:
    match = re.fullmatch(r"\s*([A-Ga-g])([#♯b♭]?)\s+(major|minor)\s*", key, re.I)
    if not match:
        return 0, (0, 2, 3, 5, 7, 8, 10)
    name, accidental, mode = match.groups()
    tonic = ({"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}[name.upper()]
             + (1 if accidental in ("#", "♯") else -1 if accidental in ("b", "♭") else 0)) % 12
    return tonic, (0, 2, 4, 5, 7, 9, 11) if mode.lower() == "major" else (0, 2, 3, 5, 7, 8, 10)


class ArrangementPlanner:
    def plan(self, brief: CreativeBrief, previous: ArrangementPlan | None = None, frozen: frozenset[str] = frozenset()) -> ArrangementPlan:
        tempo = float(brief.musical_constraints.get("tempo_bpm", 120))
        key = str(brief.musical_constraints.get("key", "C minor"))
        tonic, scale = _scale(key)
        def pitch(degree: int, octave: int) -> int:
            return 12 * octave + tonic + scale[degree % 7] + 12 * (degree // 7)

        # Feedback revises the same initial sketch; it must not reseed it.
        seed_content = {"intent": re.sub(r"\s*\[feedback: .*\]$", "", brief.intent, flags=re.I | re.S),
                        "emotional_dimensions": brief.emotional_dimensions,
                        "musical_constraints": brief.musical_constraints}
        seed = hashlib.sha256(json.dumps(seed_content, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()).digest()
        rng = random.Random(int.from_bytes(seed, "big"))
        emotions = brief.emotional_dimensions
        def level(name: str) -> float:
            return max(0.0, min(1.0, float(emotions.get(name, 0))))
        bright = level("brightness") + level("playfulness") - level("darkness")
        tense = level("tension")
        energy_base = level("energy") + .5 * level("playfulness")
        register = 1 if bright > .25 else -1 if bright < -.25 else 0
        velocity = round(8 * energy_base + 4 * tense)
        drum_seed = [Note(pitch=p, start=s, duration=.18, velocity=max(1, min(127, v + velocity))) for p, s, v in [(36,0,112),(42,.5,72),(42,1.5,70),(38,2,105),(42,2.5,76),(42,3.5,72)]]
        bass_seed = [Note(pitch=pitch(d, 3), start=s, duration=.8, velocity=92 + velocity) for d, s in [(0,0),(0,1),(2,2),(4,3)]]
        harmony_seed = [Note(pitch=pitch(d, 4 + register), start=0, duration=3.8, velocity=54 + velocity) for d in (0,2,4)]
        melody_seed = [Note(pitch=pitch(d, 5 + register), start=s, duration=.45, velocity=78 + velocity) for d, s in [(0,.5),(2,1.25),(4,2),(rng.choice((3, 5)),3)]]
        if bright > .25 or energy_base > .4:
            melody_seed.append(Note(pitch=pitch(1, 5 + register), start=3.5, duration=.25, velocity=74 + velocity))
            bass_seed.append(Note(pitch=pitch(4, 3), start=3.5, duration=.35, velocity=82 + velocity))
        if tense > .25:
            harmony_seed.append(Note(pitch=pitch(1, 4 + register), start=0, duration=3.8, velocity=48 + velocity))
        # The demo appends feedback after interpretation; extract only that suffix
        # so prompt adjectives do not accidentally act as revision instructions.
        match = re.search(r"\[feedback: (.*)\]$", brief.intent, flags=re.I | re.S)
        feedback = match.group(1) if match else ""
        dimensions = parse_feedback(feedback)
        density = dimensions.get("density", 0)
        energy = dimensions.get("energy", 0)
        brightness = dimensions.get("brightness", 0)
        tension = dimensions.get("tension", 0)
        bars = 8 + 4 * dimensions.get("length", 0)

        # Density changes note count and rhythmic subdivision. A named part is
        # revised on its own; otherwise the bass, drums and motif all respond.
        named = {role for role, words in {
            "bass": ("bass",), "drums": ("drum", "drums"),
            "melody": ("melody", "motif"), "harmony": ("harmony", "pad"),
        }.items() if any(re.search(r"\b" + word + r"\b", feedback.lower()) for word in words)}
        def targeted(role: str) -> bool:
            return not named or role in named

        if density < 0:
            if targeted("drums"):
                drum_seed = [n for n in drum_seed if n.pitch != 42 or n.start in (.5, 2.5)]
            if targeted("bass"):
                bass_seed = [n.model_copy(update={"duration": 1.6}) for n in bass_seed if n.start in (0, 2)]
            if targeted("melody"):
                melody_seed = [n for i, n in enumerate(melody_seed) if i % 2 == 0]
        elif density > 0:
            if targeted("drums"):
                drum_seed += [Note(pitch=42, start=s, duration=.18, velocity=65) for s in (1, 2, 3)]
            if targeted("bass"):
                bass_seed += [Note(pitch=p, start=s, duration=.4, velocity=82) for p, s in ((pitch(0, 3),.5), (pitch(2, 3),2.5))]
            if targeted("melody"):
                melody_seed += [Note(pitch=pitch(3, 5 + register), start=2.5, duration=.25, velocity=74)]

        # Brightness shifts the pitched register, energy shifts velocity, and
        # tension adds/removes a dissonant harmony tone and motif articulation.
        def shape(seed: list[Note], role: str) -> list[Note]:
            shaped = []
            for note in seed:
                pitch = note.pitch + (brightness * (3 if role == "bass" else 5) if role != "drums" and targeted(role) else 0)
                velocity = max(1, min(127, note.velocity + 15 * energy))
                duration = note.duration
                if role == "melody" and tension:
                    duration = .25 if tension > 0 else .7
                shaped.append(note.model_copy(update={"pitch": pitch, "velocity": velocity, "duration": duration}))
            return shaped

        if tension > 0:
            harmony_seed.append(Note(pitch=pitch(1, 4 + register), start=0, duration=3.8, velocity=48))
        elif tension < 0:
            harmony_seed = [n for n in harmony_seed if n.pitch != pitch(2, 4 + register)]
        drum_seed = shape(drum_seed, "drums")
        bass_seed = shape(bass_seed, "bass")
        harmony_seed = shape(harmony_seed, "harmony")
        melody_seed = shape(melody_seed, "melody")
        melody_notes = _repeat(melody_seed, bars)
        if re.search(r"\bfinal[- ]bar\b", feedback.lower()) and re.search(r"\b(motif|melody|variation)\b", feedback.lower()):
            melody_notes += [Note(pitch=pitch(4, 5 + register) + brightness * 5, start=(bars - 1) * 4 + 2.5, duration=.45, velocity=max(1, min(127, 84 + 15 * energy)))]
        tracks = [
            TrackPlan(name="NOCTURNE Drums", role="drums", instrument="Ableton Core Kit", notes=_repeat(drum_seed, bars)),
            TrackPlan(name="NOCTURNE Bass", role="bass", instrument="Operator", notes=_repeat(bass_seed, bars)),
            TrackPlan(name="NOCTURNE Atmosphere", role="harmony", instrument="Wavetable", notes=_repeat(harmony_seed, bars)),
            TrackPlan(name="NOCTURNE Motif", role="melody", instrument="Operator", notes=melody_notes),
        ]
        if previous is not None:
            prior = {track.role: track for track in previous.tracks}
            for track in tracks:
                if track.role in frozen and track.role in prior:
                    track.notes = [note.model_copy(deep=True) for note in prior[track.role].notes]
        return ArrangementPlan(title="NOCTURNE eight-bar sketch" if bars == 8 else f"NOCTURNE {bars}-bar sketch", tempo=tempo, bars=bars, key=key, tracks=tracks,
                               rationale=["Low register anchors the pulse.", "Sustained harmony leaves room for the motif.", "Final-bar variation can be added during refinement."])

    def song(self, brief: CreativeBrief, form: str | None = None, groove: str | None = None) -> ArrangementPlan:
        """Compose a deterministic, section-based arrangement in absolute beats."""
        from .models import SongSection

        key = str(brief.musical_constraints.get("key", "C minor"))
        tonic, scale = _scale(key)
        seed_content = {"intent": re.sub(r"\s*\[feedback: .*\]$", "", brief.intent, flags=re.I | re.S),
                        "emotional_dimensions": brief.emotional_dimensions,
                        "musical_constraints": brief.musical_constraints}
        seed = hashlib.sha256(json.dumps(seed_content, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()).digest()
        rng = random.Random(int.from_bytes(seed, "big"))
        text = seed_content["intent"].lower()
        if form is None:
            from .song import requested_form
            if requested_form(text) == "pop84":
                form = "pop84"
        if form not in (None, "edm", "club", "pop", "pop84"):
            raise ValueError("form must be edm, club, pop, pop84, or None")
        if groove is None:
            for pattern, name in ((r"\btrap\b", "trap"), (r"\bdubstep\b", "dubstep"),
                                  (r"\b(?:drum and bass|dnb)\b", "dnb"),
                                  (r"\b(?:dembow|reggaeton)\b", "dembow"),
                                  (r"\bhouse\b", "house")):
                if re.search(pattern, text):
                    groove = name
                    break
        if groove is not None and groove not in GROOVE_PRESETS:
            raise ValueError(f"unknown groove: {groove}")
        pop = bool(re.search(r"\b(song|vocal|vocals|singer|singing|pop|chorus)\b", text)) and not bool(re.search(r"\b(edm|dance|beat)\b", text))
        templates = ([("intro", 4, .35), ("verse", 8, .5), ("pre-chorus", 4, .7), ("chorus", 8, 1),
                      ("verse", 8, .5), ("chorus", 8, 1), ("bridge", 4, .4), ("chorus", 8, 1), ("outro", 4, .3)] if pop else
                     [("intro", 4, .35), ("verse", 8, .5), ("build", 8, .75), ("drop", 8, 1),
                      ("breakdown", 4, .25), ("drop", 8, 1), ("outro", 4, .3)])
        if form == "pop" and not pop:
            templates = [("intro", 4, .35), ("verse", 8, .5), ("pre-chorus", 4, .7), ("chorus", 8, 1), ("verse", 8, .5), ("chorus", 8, 1), ("bridge", 4, .4), ("chorus", 8, 1), ("outro", 4, .3)]
        elif form == "edm" and pop:
            templates = [("intro", 4, .35), ("verse", 8, .5), ("build", 8, .75), ("drop", 8, 1), ("breakdown", 4, .25), ("drop", 8, 1), ("outro", 4, .3)]
        elif form == "club":
            templates = [("intro", 16, .35), ("build", 8, .75), ("drop", 16, 1), ("breakdown", 16, .25), ("build", 8, .75), ("drop", 16, 1), ("outro", 16, .3)]
        if form == "pop84":
            # Labelled 84-bar inference from Hit Songs Deconstructed 2024 data.
            tempo = brief.musical_constraints.get("tempo_bpm")
            first_verse = 8 if tempo is not None and float(tempo) < 95 else 16
            # Postchorus inherits chorus energy; prechorus is the pop pre-chorus.
            energies = {"intro": .35, "verse": .5, "prechorus": .7,
                        "chorus": 1, "postchorus": 1, "bridge": .4, "outro": .3}
            templates = [(name, bars, energies[name]) for name, bars in (
                ("intro", 4), ("verse", first_verse), ("prechorus", 4),
                ("chorus", 8), ("postchorus", 4), ("verse", 8),
                ("prechorus", 4), ("chorus", 8), ("postchorus", 4),
                ("bridge", 8), ("chorus", 8), ("postchorus", 4), ("outro", 4))]
        contrast = form in ("pop", "pop84") or (form is None and pop)
        requested_form = form
        form = []
        bar = 0
        for name, bars, energy in templates:
            form.append(SongSection(name=name, role=name, start_bar=bar, bars=bars, energy=energy))
            bar += bars
        emotions = brief.emotional_dimensions
        def mood_words(words):
            return any(re.search(r"\b" + word + r"\b", text) for word in words)
        if key.lower().strip().endswith("major"):
            progression_name, progression = "major", (0, 4, 5, 3)
        elif mood_words(("euphoric", "uplifting", "bright")) or max(emotions.get("brightness", 0), emotions.get("euphoria", 0), emotions.get("uplifting", 0)) >= .5:
            progression_name, progression = "euphoric", (0, 2, 6, 5)
        elif mood_words(("brooding", "melancholic", "melancholy", "sad")) or max(emotions.get("sadness", 0), emotions.get("melancholy", 0), emotions.get("brooding", 0)) >= .5:
            progression_name, progression = "brooding", (0, 4, 3, 6)
        elif mood_words(("driving", "anthemic", "epic")) or max(emotions.get("driving", 0), emotions.get("anthemic", 0), emotions.get("epic", 0)) >= .5:
            progression_name, progression = "driving", (0, 6, 5, 6)
        elif requested_form == "club":
            progression_name, progression = "dance", (0, 5, 6, 3)
        elif mood_words(("dark", "tense", "nocturnal")):
            progression_name, progression = "dark", (0, 5, 2, 6)
        else:
            progression_name, progression = rng.choice((
                ("dark", (0, 5, 2, 6)), ("euphoric", (0, 2, 6, 5)),
                ("brooding", (0, 4, 3, 6)), ("driving", (0, 6, 5, 6)),
                ("dance", (0, 5, 6, 3))))
        rotation = rng.randrange(4)
        progression = progression[rotation:] + progression[:rotation]
        tracks = {role: [] for role in ("drums", "bass", "harmony", "melody")}
        def pitch(degree: int, octave: int) -> int:
            return 12 * octave + tonic + scale[degree % 7] + 12 * (degree // 7)
        def add(role: str, degree: int, octave: int, start: float, duration: float, velocity: int):
            if contrast and role == "melody":
                if section.name in ("chorus", "postchorus"):
                    # Two SCALE DEGREES at generation, before MIDI mapping.
                    degree += 2
                    velocity = round(velocity * CONTRAST_HEURISTICS["chorus_velocity_factor"])
                elif section.name == "verse":
                    velocity = round(velocity * CONTRAST_HEURISTICS["verse_velocity_factor"])
            tracks[role].append(Note(pitch=pitch(degree, octave), start=start, duration=duration, velocity=max(1, min(127, velocity))))
        def drum(p: int, start: float, velocity: int):
            tracks["drums"].append(Note(pitch=p, start=start, duration=.15, velocity=velocity))
        # Generate identity once; section operators below reuse this same motif.
        rhythm = rng.choice((
            ((0, 1, 2.5, 3.5), (.5, 1.5, 2.5, 3.5)),
            ((0, .5, 2, 3), (0, 1.5, 2, 3.5)),
            ((0, 1.5, 3), (.5, 2, 3.5)),
            ((.5, 1, 2, 3.5), (0, 1, 2.5)),
            ((0, .75, 2, 2.75), (.5, 1.5, 2, 3))))
        motif = []
        degree = rng.choice((0, 2, 4))
        for motif_bar, offsets in enumerate(rhythm):
            for offset in offsets:
                target = max(0, min(6, degree + rng.choice((-2, -1, 0, 1, 2))))
                if offset in (0, 2):
                    distances = [abs(tone - target) for tone in (0, 2, 4)]
                    nearest = min(distances)
                    degree = rng.choice(tuple(tone for tone, distance in zip((0, 2, 4), distances) if distance == nearest))
                else:
                    degree = target
                motif.append((motif_bar, offset, degree))
        bass_pattern = rng.choice((
            ((0, 0, .8), (1, 0, .8), (2, 0, .8), (3, 0, .8)),
            tuple((i / 2, 7 if i % 2 else 0, .4) for i in range(8)),
            ((0, 0, .65), (1.5, 0, .4), (2.5, 7, .4), (3.5, 0, .4)),
            ((0, 0, 1.7), (2, 7, 1.7))))
        # Default groove variants only: explicit presets retain their exact application.
        kick_offsets = rng.choice(((0,), (0, 2.5), (0, 1, 2, 3)))
        hat_offsets = rng.choice(((.5, 1.5, 2.5, 3.5),
                                  tuple(i / 2 for i in range(8)),
                                  (1.5, 3.5)))
        return_index = 0
        for si, section in enumerate(form):
            next_role = form[si + 1].role if si + 1 < len(form) else None
            for local in range(section.bars):
                absolute = section.start_bar + local
                start = absolute * 4
                root = progression[(local // (2 if section.role == "verse" else 1)) % 4]
                chord = (root, root + 2, root + 4)
                energy = section.energy
                riser = next_role in ("drop", "chorus") and local >= section.bars - 2
                impact = section.role in ("drop", "chorus") and local == 0
                build = section.role == "build"
                if groove is not None:
                    preset = GROOVE_PRESETS[groove]
                    snare_velocity = int(75 + 25 * energy)
                    for part, gm_name, velocity in (
                        ("kick", "kick", int(85 + 27 * energy)),
                        ("snare", "snare", snare_velocity),
                        ("hat", "closed_hat", int(55 + 25 * energy)),
                        ("open_hat", "open_hat", int(60 + 25 * energy)),
                    ):
                        for step in preset[part]:
                            drum(GM_PERCUSSION[gm_name], start + step * .25, velocity)
                    if preset["ghost"]:
                        for step in (7, 15):
                            drum(GM_PERCUSSION["snare"], start + step * .25, ghost_velocity(snare_velocity))
                elif section.role != "breakdown":
                    if not (build and local == section.bars - 1):
                        for off in kick_offsets:
                            drum(36, start + off, int(85 + 27 * energy))
                    if build:
                        spacing = 1 if local < section.bars // 3 else .5 if local < 2 * section.bars // 3 else .25
                        if local == section.bars - 1:
                            spacing = .125
                        for i in range(int(4 / spacing)):
                            drum(38, start + i * spacing, min(120, 75 + local * 3))
                    else:
                        drum(38, start + 2, int(75 + 25 * energy))
                    for off in (hat_offsets if energy >= .7 else hat_offsets[::2]):
                        drum(42, start + off, int(55 + 25 * energy))
                    if local == section.bars - 1 and not build:
                        for off in (2.25, 2.75, 3, 3.25, 3.5, 3.75):
                            drum(38, start + off, 85 + int(15 * energy))
                    if riser:
                        for off in ([0, 1, 2, 3] if local == section.bars - 2 else [x / 2 for x in range(8)]):
                            drum(46, start + off, 65 + int(20 * energy) + (10 if local == section.bars - 1 else 0))
                for off, degree, duration in bass_pattern:
                    if energy >= .5 or off in (0, 2):
                        add("bass", root + degree, 3, start + off, duration, int(65 + 35 * energy))
                # Broken voicing, with root/fifth only in the breakdown.
                tones = (root, root + 4) if section.role == "breakdown" else chord
                for i, degree in enumerate(tones):
                    add("harmony", degree, 4 + int(energy >= .9), start + i * .75, 2.2 if i == 0 else 1.3, int(42 + 30 * energy))
                if riser:
                    for i in range(2 if local == section.bars - 2 else 4):
                        add("harmony", chord[i % 3], 5 + int(local == section.bars - 1), start + i * (2 if local == section.bars - 2 else 1), .3, 65 + i * 3)
                # One operator per two-bar return, seeded independently of section shape.
                if local % 2 == 0:
                    operator = rng.choice(("transpose", "octave", "rhythm", "tail", "rest")) if return_index else "original"
                    return_index += 1
                hook = section.role in ("drop", "chorus")
                if hook:
                    # Reuse a two-bar onset pattern for all statements. Pitch-only
                    # operators vary the answers and the second drop.
                    statement = (local % 8) // 2
                    operator = ("original", "transpose", "tail", "octave")[statement]
                    if section.role == "drop" and sum(s.role == "drop" for s in form[:si]) > 0:
                        operator = ("transpose", "tail", "octave", "transpose")[statement]
                for motif_bar, offset, degree in motif:
                    if motif_bar != local % 2:
                        continue
                    if section.role == "verse" and offset in (1, 1.5, 3.5):
                        continue
                    if not hook and operator == "rest" and offset == 2.5:
                        continue
                    d = degree + (2 if operator == "transpose" else 0)
                    if operator == "tail" and offset == 3.5:
                        d = 4 if degree != 4 else 2
                    # Map motif degrees to the current chord; occasional passing tones retain contour.
                    d = root + d
                    shift = .25 if operator == "rhythm" and offset < 3.5 else 0
                    octave = 5 + int(energy >= .9) - int(section.role == "verse") + int(operator == "octave")
                    add("melody", d, octave, start + offset + shift, .35, int(60 + 30 * energy))
                if impact:
                    drum(49, start, 127)
            # Without a preset, breakdown drums are deliberately silent.
        # Guard against repeated bars even when seeded operators happen to coincide.
        previous_bars: list[tuple] = []
        for absolute in range(bar):
            notes = [n for n in tracks["melody"] if absolute * 4 <= n.start < (absolute + 1) * 4]
            signature = tuple((n.pitch, n.start - absolute * 4, n.duration) for n in notes)
            if len(previous_bars) >= 2 and signature == previous_bars[-1] == previous_bars[-2]:
                if notes:
                    notes[-1].pitch += 12 if notes[-1].pitch <= 115 else -12
                else:
                    section = next(s for s in form if s.start_bar <= absolute < s.start_bar + s.bars)
                    root = progression[((absolute - section.start_bar) // (2 if section.role == "verse" else 1)) % 4]
                    add("melody", root, 5, absolute * 4 + 3, .35, 70)
                    notes = [tracks["melody"][-1]]
                signature = tuple((n.pitch, n.start - absolute * 4, n.duration) for n in notes)
            previous_bars.append(signature)
        parts = [("drums", "NOCTURNE Drums", "Ableton Core Kit"), ("bass", "NOCTURNE Bass", "Operator"),
                 ("harmony", "NOCTURNE Atmosphere", "Wavetable"), ("melody", "NOCTURNE Motif", "Operator")]
        return ArrangementPlan(title="NOCTURNE song", tempo=float(brief.musical_constraints.get("tempo_bpm", 120)), bars=bar, key=key,
                               groove_name=groove, progression_name=progression_name, progression=list(progression), form=form, tracks=[TrackPlan(name=name, role=role, instrument=instrument, notes=tracks[role]) for role, name, instrument in parts],
                               rationale=["Section energy shapes register, velocity and density.", "Harmony follows a diatonic four-chord progression."])
