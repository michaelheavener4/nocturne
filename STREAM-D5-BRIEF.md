SHARED CONTRACT (all Build 5 streams; names pinned per the Finding 004 lesson):
- Planner entry: ArrangementPlanner.song(brief, form=None); form in {"edm","club","pop",None}. Delegate: song.plan_song(brief, form=None).
- Plan JSON gains: "progression_name" (str) and "progression" (list of scale-degree indices, one chord cycle).
- Natural-minor degree indices: i=0, ii=1, III=2, iv=3, v=4, VI=5, VII=6.
- Progression library (minor): dark i-VI-III-VII (0,5,2,6); dance i-VI-VII-iv (0,5,6,3) with rotations allowed; euphoric i-III-VII-VI (0,2,6,5); driving i-VII-VI-VII (0,6,5,6); brooding i-v-iv-VII (0,4,3,6). Major default I-V-vi-IV unchanged. Never default to a ii chord.
- Mood selection from brief language/dimensions: euphoric/uplifting/bright -> euphoric; brooding/melancholic/sad -> brooding; driving/anthemic/epic -> driving; form=club -> dance; otherwise dark (minor) or the major default.
- Hook architecture (drop/chorus sections): melody in 8-bar phrases of 2-bar statements S1 S2 S3 S4. S2 and S4 keep S1's exact rhythm signature (onset pattern) and vary pitches via the existing variation operators. S1 contains at least one melodic leap of 5+ semitones. S3 may contrast.
- Build anatomy (edm build sections and all club builds): snare density ramps across the build (quarter spacing, then 8ths, then 16ths, final bar densest), riser continues, kick drum silent in the final build bar, impact (velocity peak) on bar 1 of the following drop/chorus.
- Club form sections (bars): intro 16, build 8, drop 16, breakdown 16, build 8, drop 16, outro 16 = 96. Second drop keeps the hook rhythm signature with one added layer or variation.
- Repetition analysis: repetition_report(plan) returns {identical_cell_share, range_semitones, stepwise_only, repetitive_flag}; 2-bar melody cells; repetitive_flag when share > 0.75 with no cadential variation (last cell == first cell) OR (range < 5 semitones AND stepwise_only).
- The 8-bar groove path is byte-untouched: baseline 91c023a806e8b839ae686232e1709ff1 must not move. Song hashes will move; that is expected and gets documented in Finding 005.
- Source research: bridge rows R-001 (hook repetition/arch), R-002 (EDM anatomy, Grimes maps), R-003 (minor loops + mood map), delivered 2026-10-26 by Research Slave via Yay and vetted by the coordinator.

STREAM D5 (Mac local model, muse-mac worktree): owns src/nocturne/songbook.py ONLY.
Extend the songbook with research-backed data, in the module's existing style, with accessor functions like the existing ones:
(1) PROGRESSIONS: add the five minor loops from the shared contract (dark, dance incl. its three rotations as separate entries, euphoric, driving, brooding), each entry carrying its degree tuple and mood tags drawn ONLY from {dark, tense, euphoric, brooding, driving, anthemic, melancholic}.
(2) BUILD_ANATOMY: a dict capturing the R-002 build map: snare subdivision steps across a build (["quarter","eighth","sixteenth","thirty-second"] by build fraction), kick_cut_final_bar True, riser spans the full build, impact on the first bar after the build.
(3) HOOK_PHRASE: constants for the R-001 hook rule: statement_bars 2, phrase_statements 4, varied_statements (2, 4), rhythm_fixed_on_vary True, min_leap_semitones 5.
Validation you must pass before committing: every degree within 0..6; the dance rotations are exact rotations of (0,5,6,3); every mood tag in the fixed set; the repo test suite passes. Commit locally on this branch with a clear message; the coordinator pushes.
