SHARED CONTRACT (Build 6, stream C6; names pinned per the Finding 004 lesson):
Baseline: main @ 76e921b (A6 grooves + B6 gate already merged). Groove baseline
91c023a806e8b839ae686232e1709ff1 must not move. Default song behaviour changes
ONLY where this contract says so; forms edm/club/pop stay byte-identical.

1. NEW FORM "pop84" (from vetted R-007; the 84-bar template is a labelled
   inference from Hit Songs Deconstructed 2024 data, arithmetic verified):
   sections in order (name, bars):
   intro 4, verse 16, prechorus 4, chorus 8, postchorus 4, verse 8,
   prechorus 4, chorus 8, postchorus 4, bridge 8, chorus 8, postchorus 4,
   outro 4 = 84 bars total.
   - ArrangementPlanner.song(brief, form="pop84") and song.plan_song(..., form="pop84")
     accept it; song.SONG_FORMS gains "pop84"; song.requested_form returns "pop84"
     when the brief text contains "chart pop" or "pop84".
   - Tempo fix from the vetting: if the brief/plan tempo is known and below
     95 BPM, verse 1 shortens to 8 bars (total 76) so the first chorus starts
     within 60 seconds. If no tempo is known, keep 16. Record what happened:
     the plan's form list is the proof either way.
   - Section energy: reuse the existing pop template's per-section energy
     values by section name (chorus highest, intro/outro lowest).

2. CHORUS/VERSE CONTRAST (from vetted R-006; multi-axis model, timbre first
   in the research, but the implementable axes here are loudness + register):
   - CONTRAST_HEURISTICS = {"chorus_velocity_factor": 1.10,
     "chorus_register_semitones": 2, "verse_velocity_factor": 0.95}
     in arrangement.py, with a comment stating these are labelled heuristics,
     NOT research-measured defaults, and that the underlying corpus is
     1955-1991 rock/pop.
   - In the song path, for sections named "chorus" or "postchorus": melody
     note velocities scale by chorus_velocity_factor (clamp 127) and the
     melody register rises by 2 SCALE DEGREES at generation time (the
     direction of the vetted +2 semitone tessitura heuristic, implemented
     in scale steps so every note stays in key; a post-hoc semitone
     transpose would break the song-truth in-key tests, as the first C6
     seat's analysis caught). For "verse" sections: melody velocities
     scale by verse_velocity_factor. Other sections and other tracks
     (drums/bass/harmony) are untouched. This applies to forms pop and pop84
     ONLY (edm/club use drop sections, untouched; the existing pop form's
     hashes WILL move, that is expected and gets documented).
   - contrast_report(plan) in the analysis module (analysis.py) returns
     {section_name: {"mean_melody_velocity": float, "mean_melody_pitch": float}}
     aggregated per section NAME across the plan, melody track only, so a
     gate can assert chorus > verse on both axes.

STREAM C6 (Codex, this worktree; reassigned 2026-10-29 after the Grok seat
hit its free Grok Build usage limit before writing any code): owns src/nocturne/arrangement.py,
src/nocturne/song.py, src/nocturne/analysis.py, src/nocturne/models.py only
if unavoidable. Do NOT touch grooves.py, cli.py, session.py, render.py,
tests/, tools/.
Proof required in your final summary: pop84 section list + total bars from a
real plan; a pop song's contrast_report showing chorus mean velocity and
mean pitch both above verse; edm song md5 unchanged from main 76e921b
behaviour; club song md5 unchanged; groove baseline still
91c023a806e8b839ae686232e1709ff1; existing pytest suite green.
Scratch files inside this worktree only, never /tmp for working state.
Leave all changes uncommitted in the working tree; the coordinator reviews
and commits.
