# Stream D4 brief: the songbook data module (Build 4, Mac local model seat)

You are the local-model seat of the fleet. Your deliverable is ONE new
file, src/muse/songbook.py, pure data plus tiny accessors, stdlib only.
Do not touch any other file. The other streams own the planner, the
gate, and the wiring; your module is the musical content library the
planner can draw on: chord progressions, voicings, drum fills, riser
shapes, and per-section energy curves for the edm and pop forms.

Required contents:
- PROGRESSIONS: dict keyed by mode ("minor", "major") -> list of
  progressions; each progression is a list of (degree, quality) chords,
  degree 1..7, quality in {"maj","min","dim"}. Include the defaults
  i-VI-III-VII (minor) and I-V-vi-IV (major) plus at least 3 variants
  per mode.
- VOICINGS: dict keyed by quality -> list of chord-tone offsets in
  semitones from the root, at least 2 voicings per quality, every
  offset within 0..15, always including 0.
- FILL_PATTERNS: at least 4 one-bar drum fills; each is a list of
  (step, drum_note, velocity) with steps 0..15 (16th-note grid),
  drum_note a GM drum pitch (35..81), velocity 1..127; every fill
  ends with a hit on step 15 or 14 and gets denser toward the end.
- RISER: a dict describing a 2-bar riser: density ramp and register
  climb as lists of 8 eighth-note values each, both non-decreasing,
  ending at their max.
- SECTION_ENERGY: dict keyed by form ("edm", "pop") -> dict of section
  role -> energy 0..1, covering intro, verse, build, drop, chorus,
  pre-chorus, breakdown, bridge, outro where the form uses them;
  drop/chorus >= 0.85, intro/outro <= 0.45.
- Accessors: progression(mode, index=0), voicing(quality, index=0),
  fill(index=0), section_energy(form, role) with sane defaults.

Validation (a driver runs these; failing them sends the errors back):
imports clean; every progression chord tone set is consistent with
its quality; fills sorted by step with steps in range; riser lists
non-decreasing length 8; energies in range with the drop/intro rules.
