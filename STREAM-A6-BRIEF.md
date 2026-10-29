SHARED CONTRACT (Build 6 streams; names pinned per the Finding 004 lesson):
- New module: src/nocturne/grooves.py. Nothing else creates it.
- GM_PERCUSSION = {"kick":36, "rim":37, "snare":38, "clap":39, "closed_hat":42,
  "open_hat":46, "crash":49, "ride":51, "maracas":70, "shaker":82}
  (vetting correction: shaker is 82, maracas is 70; a source research item had this wrong).
- One bar = 16 steps; step index 0..15; step duration 0.25 beats.
- GROOVE_PRESETS: dict of name -> {"kick": [steps], "snare": [steps], "hat": [steps],
  "open_hat": [steps], "ghost": bool}. Pinned patterns:
  house:    kick [0,4,8,12], snare [4,12], hat every step, open_hat [2,6,10,14], ghost False
  backbeat: kick [0,8], snare [4,12], hat [0,2,4,6,8,10,12,14], open_hat [], ghost False
  trap:     kick [0,10], snare [8], hat every step, open_hat [], ghost True (half-time feel)
  dubstep:  kick [0], snare [8], hat [0,2,4,6,8,10,12,14], open_hat [], ghost False (half-time)
  dnb:      kick [0,10], snare [4,12], hat every step, open_hat [], ghost True
  dembow:   kick [0,8], snare [3,6,11,14], hat [0,2,4,6,8,10,12,14], open_hat [], ghost False
  dembow_b: kick [0,8], snare [0,3,6,8,11,14], hat same as dembow, open_hat [], ghost False
- GENRE_SWING = {"house":54, "backbeat":50, "trap":52, "dubstep":50, "dnb":51, "dembow":50}
  Practitioner-consensus editable defaults. Label that in a comment; never cite as measured fact.
- apply_swing(notes, swing_pct): delays notes whose start falls on an odd 16th step
  by (swing_pct - 50) / 100 * 0.5 beats. 50 = no movement. Returns new notes, input unmodified.
- ghost_velocity(backbeat_velocity) = max(1, int(backbeat_velocity * 0.32))
  (one scale only: ~32 percent, inside the vetted 25-40 percent band).
- BASS_GRIDS = {"offbeat": [2,6,10,14], "double_offbeat": [2,3,6,7,10,11,14,15],
  "rolling": list(range(16))}  (16th steps where bass plays against a four-on-the-floor kick)
- sidechain_release_ms(bpm, requested_ms=300) = min(requested_ms, 0.9 * 60000 / bpm)
  (pump release must recover before the next kick; vetted clamp).
- MONO_SUB_HZ = 120 (kick + sub only below this; a documented constant, no DSP).
- Wiring: ArrangementPlanner.song(brief, form=None, groove=None) and
  song.plan_song(brief, form=None, groove=None). If groove is None, infer from brief
  text keywords: "trap" -> trap, "dubstep" -> dubstep, "drum and bass"/"dnb" -> dnb,
  "dembow"/"reggaeton" -> dembow, "house" -> house; else None.
  When a groove is active, the SONG path drum writer uses the preset steps per bar
  (hat velocity lower than snare; ghost notes at ghost_velocity when ghost is True,
  placed on steps 7 and 15 as snare ghosts), and the plan records "groove_name".
  When groove resolves to None, song output must stay byte-identical to Build 5.
- The 8-bar groove path is byte-untouched: baseline 91c023a806e8b839ae686232e1709ff1 must not move.
- Scratch files go inside this worktree only. Never write to /tmp for working state.

STREAM A6 (Codex, this worktree): owns src/nocturne/grooves.py (new),
src/nocturne/arrangement.py, src/nocturne/song.py, src/nocturne/models.py if the
plan dict needs no change skip it. Do NOT touch cli.py, session.py, render.py,
tests/, tools/.
Implement the shared contract exactly: grooves module + song-path wiring.
Proof required in your final summary: groove baseline still
91c023a806e8b839ae686232e1709ff1; a trap-groove song md5 and its snare steps per
bar (must be only step 8 within each bar, ghosts aside); a default (no-groove)
song md5 identical across two runs and equal to the Build 5 behaviour; existing
pytest suite green.
Leave all changes uncommitted in the working tree; the coordinator reviews and commits.
