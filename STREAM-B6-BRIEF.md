STREAM B6 (OpenCode seat via connector, coordinator lands the files): owns
tests/test_groove_research.py (new) and Gate v6 probes in tools/verify.py.
Do NOT touch src/.

Write pytest tests for the Build 6 shared contract (implemented by A6 in
src/nocturne/grooves.py; the tests must FAIL on Build 5 main where grooves.py
does not exist, and PASS once A6 lands):
- GM_PERCUSSION exact values, in particular shaker == 82 and maracas == 70.
- GROOVE_PRESETS exact step lists for house, trap, dubstep, dnb, dembow, dembow_b
  (contract: house kick [0,4,8,12] snare [4,12] open_hat [2,6,10,14]; trap kick
  [0,10] snare [8]; dubstep kick [0] snare [8]; dnb kick [0,10] snare [4,12];
  dembow snare [3,6,11,14]; dembow_b snare [0,3,6,8,11,14]).
- BASS_GRIDS: offbeat == [2,6,10,14]; rolling has 16 steps; double_offbeat is a
  superset of offbeat.
- ghost_velocity(100) is between 25 and 40, and ghost_velocity scales monotonically.
- apply_swing: at 50 nothing moves; at 58 a note on an odd step moves later and a
  note on an even step does not move; input list unmodified.
- sidechain_release_ms(128, 300) < 469 and equals 0.9 * 60000 / 128 capped logic:
  sidechain_release_ms(60, 300) == 300 (request under the cap passes through).
- MONO_SUB_HZ == 120.
- GENRE_SWING has all six preset names and every value in 50..58.

Style: plain pytest functions, imports only from nocturne.grooves plus stdlib,
no fixtures from other test files, deterministic.
The coordinator will run the file against Build 5 main (expect failures) and
against the merged Build 6 tree (expect all pass), and will report both.
