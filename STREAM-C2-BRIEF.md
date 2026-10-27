# Stream C2 — Render: hearing without a DAW (seat: Grok Build)

Branch: `build2-render`. You own: src/muse/render.py (NEW) and the wiring
in src/muse/cli.py. Nothing else: no arrangement/intent/tests/tools edits.

## Deliverable
1. `muse render <file.mid> [--out file.wav] [--soundfont path.sf2]` —
   renders MIDI to WAV by invoking the system fluidsynth binary.
   Soundfont resolution order: --soundfont flag, $MUSE_SOUNDFONT,
   any *.sf2 under ~/.local/share/muse/soundfonts/, then
   /usr/share/soundfonts/FluidR3_GM.sf2. If fluidsynth or a soundfont is
   missing, exit nonzero with a message that names exactly what to install.
2. `muse demo` gains `--render`: after writing the MIDI, render it to a
   sibling .wav via the same code path.
3. Validate locally and say how in the commit: render the demo baseline,
   assert the WAV has a RIFF header and nonzero length/duration. If no
   soundfont exists on this machine yet, still ship correct code and prove
   the failure message works; the coordinator will supply a soundfont for
   the final end-to-end check.
Commit early and often on `build2-render`; messages state what you ran.
