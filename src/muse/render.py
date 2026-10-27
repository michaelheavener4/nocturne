"""Render MIDI to WAV by invoking the system fluidsynth binary."""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path
from typing import NamedTuple

# Arch soundfont-fluid installs FluidR3 here. Debian's fluid-soundfont-gm
# uses a different path; point MUSE_SOUNDFONT at it or copy the file into
# the user soundfont directory.
SYSTEM_SOUNDFONT = Path("/usr/share/soundfonts/FluidR3_GM.sf2")

FLUIDSYNTH_MISSING = "fluidsynth is not installed. Install the fluidsynth package."


class RenderError(RuntimeError):
    """fluidsynth or a SoundFont is missing, or the render did not produce a WAV."""


class RenderedWav(NamedTuple):
    wav: Path
    soundfont: Path


def user_soundfont_dir() -> Path:
    return Path.home() / ".local" / "share" / "muse" / "soundfonts"


def _soundfont_install_message(prefix: str) -> str:
    directory = user_soundfont_dir()
    return (
        f"{prefix} Install soundfont-fluid (Arch; provides {SYSTEM_SOUNDFONT}) "
        "or fluid-soundfont-gm (Debian/Ubuntu), "
        f"place a .sf2 file in {directory}/, or set MUSE_SOUNDFONT."
    )


def _existing_file(path: Path) -> Path | None:
    try:
        if path.is_file():
            return path
    except OSError:
        return None
    return None


def resolve_soundfont(explicit: str | Path | None = None) -> Path:
    """First existing SoundFont wins.

    Order: --soundfont, $MUSE_SOUNDFONT, any *.sf2 under the user soundfont
    directory, then the system FluidR3_GM file. An explicit path that does
    not exist is an error: falling through would play a different font.
    """
    if explicit is not None and str(explicit).strip():
        path = Path(explicit).expanduser()
        found = _existing_file(path)
        if found is None:
            raise RenderError(_soundfont_install_message(f"SoundFont not found: {path}."))
        return found

    env = os.environ.get("MUSE_SOUNDFONT", "").strip()
    if env:
        path = Path(env).expanduser()
        found = _existing_file(path)
        if found is None:
            raise RenderError(_soundfont_install_message(f"MUSE_SOUNDFONT is not a SoundFont file: {path}."))
        return found

    directory = user_soundfont_dir()
    if directory.is_dir():
        try:
            fonts = sorted(
                (item for item in directory.rglob("*") if item.is_file() and item.suffix.lower() == ".sf2"),
                key=lambda item: str(item).lower(),
            )
        except OSError:
            fonts = []
        if fonts:
            return fonts[0]

    found = _existing_file(SYSTEM_SOUNDFONT)
    if found is not None:
        return found
    raise RenderError(_soundfont_install_message("No SoundFont found."))


def find_fluidsynth() -> str:
    binary = shutil.which("fluidsynth")
    if not binary:
        raise RenderError(FLUIDSYNTH_MISSING)
    return binary


def _reject_bad_wav(path: Path) -> None:
    try:
        handle = path.open("rb")
    except OSError as exc:
        raise RenderError(f"fluidsynth did not write a RIFF WAV at {path} ({exc})") from exc
    with handle:
        header = handle.read(12)
        if len(header) < 12 or header[:4] != b"RIFF" or header[8:12] != b"WAVE":
            raise RenderError(f"fluidsynth did not write a RIFF WAV at {path}")
        while True:
            chunk = handle.read(8)
            if len(chunk) < 8:
                raise RenderError(f"fluidsynth wrote a WAV with no audio data at {path}")
            kind = chunk[:4]
            size = int.from_bytes(chunk[4:8], "little")
            if kind == b"data":
                if size <= 0:
                    raise RenderError(f"fluidsynth wrote a zero-length WAV at {path}")
                return
            handle.seek(size + (size & 1), os.SEEK_CUR)


def _fluidsynth_detail(stderr: str, stdout: str) -> str:
    text = stderr or stdout or ""
    lines = [line for line in text.splitlines() if line.strip() and not line.startswith("ALSA lib ")]
    return "\n".join(lines).strip()


def render_midi(
    midi_path: str | Path,
    out_path: str | Path | None = None,
    soundfont: str | Path | None = None,
) -> RenderedWav:
    """Render midi_path to a WAV file.

    out_path defaults to a sibling .wav. soundfont follows resolve_soundfont.
    """
    midi = Path(midi_path)
    if not midi.is_file():
        raise RenderError(f"MIDI file not found: {midi}")
    wav = Path(out_path) if out_path else midi.with_suffix(".wav")
    if wav.exists() and wav.is_dir():
        raise RenderError(f"Output path is a directory: {wav}")
    wav.parent.mkdir(parents=True, exist_ok=True)

    problems: list[str] = []
    binary: str | None
    font: Path | None
    try:
        binary = find_fluidsynth()
    except RenderError as exc:
        binary = None
        problems.append(str(exc))
    try:
        font = resolve_soundfont(soundfont)
    except RenderError as exc:
        font = None
        problems.append(str(exc))
    if binary is None or font is None:
        raise RenderError(" ".join(problems))

    command = [
        binary,
        "-ni",
        "-q",
        "-F",
        str(wav),
        "-T",
        "wav",
        str(font),
        str(midi),
    ]
    try:
        completed = subprocess.run(
            command,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            errors="replace",
        )
    except OSError as exc:
        raise RenderError(f"{FLUIDSYNTH_MISSING} ({exc})") from exc
    if completed.returncode != 0:
        wav.unlink(missing_ok=True)
        detail = _fluidsynth_detail(completed.stderr, completed.stdout)
        message = f"fluidsynth failed (exit {completed.returncode}) rendering {midi}"
        if detail:
            message = f"{message}: {detail}"
        raise RenderError(message)
    try:
        _reject_bad_wav(wav)
    except RenderError:
        wav.unlink(missing_ok=True)
        raise
    return RenderedWav(wav, font)
