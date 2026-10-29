# STREAM C7 BRIEF — song JSON export for players (Grok seat, SMALL slice)

You are building in a worktree of NOCTURNE (Python, src/nocturne). Goal:
any web player (SONGPOST, heavener.co) needs note data without parsing
MIDI. Add ONE module and ONE test file. Nothing else.

DELIVERABLES:
1. src/nocturne/export.py with `song_to_json(plan, brief=None) -> dict`
   returning a JSON-serializable dict: title (from brief intent text if
   given, else plan metadata or "Untitled"), tempo_bpm, key/mode if the
   plan carries them, form (ordered list of {name, bars}), tracks: a list
   of {name, notes: [{pitch, start_beats, duration_beats, velocity}]}
   covering melody/bass/drums as the plan represents them, and
   contrast: the existing analysis.contrast_report(plan) output when the
   form is pop/pop84, else null. Use the plan's existing structures; read
   arrangement.py / analysis.py / song.py to match real field names.
   Deterministic: same plan in, same dict out (stable ordering).
2. tests/test_export.py: proves (a) JSON round-trips through json.dumps,
   (b) note counts per track match the plan's own note lists, (c) a pop84
   plan yields non-null contrast with chorus above verse, (d) an EDM plan
   still exports with contrast null or present per your implementation
   (assert whichever the code does, honestly).

Rules: no changes to existing files. No musical behavior changes; the
full existing suite must stay green. End with a summary of the JSON shape
and your test results. Leave changes uncommitted.
