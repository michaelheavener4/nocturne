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

STREAM A5 (Codex, planner worktree): owns arrangement.py, intent.py, models.py, and the analysis module. Do not touch cli.py, song.py, session.py, render.py, tests/, tools/.
Implement: (1) the progression library + mood selection from the shared contract, recorded on the plan as progression + progression_name; (2) hook architecture in drop/chorus sections (S1 S2 S3 S4 statements, S2/S4 rhythm-identical pitch-varied, S1 leap >= 5 semitones); (3) build anatomy (snare ramp, kick cut, impact) in edm builds and club builds; (4) the club form template behind the form parameter; (5) repetition_report(plan) in the analysis module per the contract.
Proof required in your final summary: one song md5 per mood keyword (dark, euphoric, brooding, driving) plus a club-form song with its section list; two runs of the club song identical; groove baseline still 91c023a806e8b839ae686232e1709ff1; existing suite green.
Leave all changes uncommitted in the working tree; the coordinator reviews and commits.
