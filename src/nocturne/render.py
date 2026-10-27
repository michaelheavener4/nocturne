"""Render MIDI to WAV by invoking the system fluidsynth binary."""

from __future__ import annotations

import os
import shutil
import struct
import subprocess
import tempfile
from pathlib import Path
from typing import NamedTuple

# Arch soundfont-fluid installs FluidR3 here. Debian's fluid-soundfont-gm
# uses a different path; point NOCTURNE_SOUNDFONT at it or copy the file into
# the user soundfont directory.
SYSTEM_SOUNDFONT = Path("/usr/share/soundfonts/FluidR3_GM.sf2")

FLUIDSYNTH_MISSING = "fluidsynth is not installed. Install the fluidsynth package."


class RenderError(RuntimeError):
    """fluidsynth or a SoundFont is missing, or the render did not produce a WAV."""


class RenderedWav(NamedTuple):
    wav: Path
    soundfont: Path
    duration_seconds: float
    size_bytes: int


def user_soundfont_dir() -> Path:
    return Path.home() / ".local" / "share" / "nocturne" / "soundfonts"


def _legacy_soundfont_dir() -> Path:
    # Pre-rename installs (when the project was called MUSE) put fonts here.
    return Path.home() / ".local" / "share" / "nocturne" / "soundfonts"


def _soundfont_install_message(prefix: str) -> str:
    directory = user_soundfont_dir()
    return (
        f"{prefix} Install soundfont-fluid (Arch; provides {SYSTEM_SOUNDFONT}) "
        "or fluid-soundfont-gm (Debian/Ubuntu), "
        f"place a .sf2 file in {directory}/, or set NOCTURNE_SOUNDFONT."
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

    Order: --soundfont, $NOCTURNE_SOUNDFONT, any *.sf2 under the user soundfont
    directory, then the system FluidR3_GM file. An explicit path that does
    not exist is an error: falling through would play a different font.
    """
    if explicit is not None and str(explicit).strip():
        path = Path(explicit).expanduser()
        found = _existing_file(path)
        if found is None:
            raise RenderError(_soundfont_install_message(f"SoundFont not found: {path}."))
        return found

    env = os.environ.get("NOCTURNE_SOUNDFONT", "").strip()
    if env:
        path = Path(env).expanduser()
        found = _existing_file(path)
        if found is None:
            raise RenderError(_soundfont_install_message(f"NOCTURNE_SOUNDFONT is not a SoundFont file: {path}."))
        return found

    for directory in (user_soundfont_dir(), _legacy_soundfont_dir()):
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


def _wav_stats(path: Path) -> tuple[float, int]:
    """Duration and size from the WAV header.

    A multi-minute song is tens of megabytes. The PCM is not loaded; the
    data-chunk size and the fmt chunk are enough.
    """
    try:
        size_bytes = path.stat().st_size
        handle = path.open("rb")
    except OSError as exc:
        raise RenderError(f"fluidsynth did not write a RIFF WAV at {path} ({exc})") from exc
    with handle:
        header = handle.read(12)
        if len(header) < 12 or header[:4] != b"RIFF" or header[8:12] != b"WAVE":
            raise RenderError(f"fluidsynth did not write a RIFF WAV at {path}")
        sample_rate = channels = bits = data_size = None
        while True:
            chunk = handle.read(8)
            if len(chunk) < 8:
                break
            kind = chunk[:4]
            size = int.from_bytes(chunk[4:8], "little")
            if kind == b"fmt ":
                fmt = handle.read(size)
                if len(fmt) < 16:
                    raise RenderError(f"fluidsynth wrote a WAV with a truncated fmt chunk at {path}")
                channels = int.from_bytes(fmt[2:4], "little")
                sample_rate = int.from_bytes(fmt[4:8], "little")
                bits = int.from_bytes(fmt[14:16], "little")
                if size & 1:
                    handle.seek(1, os.SEEK_CUR)
            elif kind == b"data":
                remaining = size_bytes - handle.tell()
                # 0xFFFFFFFF is the placeholder some writers leave for a
                # data chunk whose length is not known up front.
                if size in (0, 0xFFFFFFFF) or size > remaining:
                    size = max(0, remaining)
                data_size = size
                break
            else:
                handle.seek(size + (size & 1), os.SEEK_CUR)
        if data_size is None or data_size <= 0:
            raise RenderError(f"fluidsynth wrote a WAV with no audio data at {path}")
        if not sample_rate or not channels or not bits or bits % 8:
            raise RenderError(f"fluidsynth wrote a WAV with an unreadable fmt chunk at {path}")
        frame = channels * (bits // 8)
        duration = data_size / (sample_rate * frame)
        if duration <= 0:
            raise RenderError(f"fluidsynth wrote a zero-length WAV at {path}")
        return duration, size_bytes


def _midi_with_tempo(source: Path, bpm: float) -> bytes:
    """Return MIDI bytes with a conductor track that stamps bpm.

    write_midi stores the tempo on the plan only. fluidsynth otherwise
    plays the file at 120 bpm, and a 44-bar song at 92 bpm (~115 seconds)
    would come out short.
    """
    if not 20 <= bpm <= 300:
        raise RenderError(f"tempo {bpm} bpm is outside 20..300")
    data = source.read_bytes()
    if len(data) < 14 or data[:4] != b"MThd":
        raise RenderError(f"MIDI file has no MThd header: {source}")
    header_length = struct.unpack(">I", data[4:8])[0]
    if header_length < 6:
        raise RenderError(f"MIDI header is too short to carry a division: {source}")
    fmt, ntrks, division = struct.unpack(">HHH", data[8:14])
    if division & 0x8000:
        raise RenderError(f"MIDI file uses SMPTE timing; cannot stamp a tempo: {source}")
    pos = 8 + header_length
    tracks: list[bytes] = []
    for index in range(ntrks):
        if pos + 8 > len(data) or data[pos:pos + 4] != b"MTrk":
            raise RenderError(f"MIDI track {index} is missing: {source}")
        length = struct.unpack(">I", data[pos + 4:pos + 8])[0]
        end = pos + 8 + length
        if end > len(data):
            raise RenderError(f"MIDI track {index} is truncated: {source}")
        tracks.append(data[pos:end])
        pos = end
    mpqn = int(round(60_000_000 / bpm))
    tempo = bytes((0x00, 0xFF, 0x51, 0x03, (mpqn >> 16) & 0xFF, (mpqn >> 8) & 0xFF, mpqn & 0xFF))
    payload = tempo + b"\x00\xff\x2f\x00"
    conductor = b"MTrk" + struct.pack(">I", len(payload)) + payload
    # A format-0 file has one track; adding a conductor makes it format 1.
    out_fmt = 1 if fmt == 0 else fmt
    header = b"MThd" + struct.pack(">IHHH", 6, out_fmt, ntrks + 1, division)
    return header + conductor + b"".join(tracks)


def _fluidsynth_detail(stderr: str, stdout: str) -> str:
    text = stderr or stdout or ""
    lines = [line for line in text.splitlines() if line.strip() and not line.startswith("ALSA lib ")]
    return "\n".join(lines).strip()


def render_midi(
    midi_path: str | Path,
    out_path: str | Path | None = None,
    soundfont: str | Path | None = None,
    tempo_bpm: float | None = None,
) -> RenderedWav:
    """Render midi_path to a WAV file.

    out_path defaults to a sibling .wav. soundfont follows resolve_soundfont.
    tempo_bpm stamps a conductor track on a temporary copy so the file is
    played at the plan tempo. There is no wall-clock timeout: a 44-bar song
    at 92 bpm is about 115 seconds of audio and must be allowed to finish.
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

    # Sample-clock timing runs the player out to the last tick even when
    # synthesis is faster than realtime. lock-memory is a realtime precaution
    # and can fail while rendering a long file, so file renders turn it off.
    temporary: Path | None = None
    source = midi
    try:
        if tempo_bpm is not None:
            fd, name = tempfile.mkstemp(prefix="nocturne-render-", suffix=".mid")
            os.close(fd)
            temporary = Path(name)
            temporary.write_bytes(_midi_with_tempo(midi, float(tempo_bpm)))
            source = temporary
        command = [
            binary,
            "-ni",
            "-q",
            "-o",
            "synth.lock-memory=0",
            "-o",
            "player.timing-source=sample",
            "-F",
            str(wav),
            "-T",
            "wav",
            str(font),
            str(source),
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
            wav.unlink(missing_ok=True)
            raise RenderError(f"{FLUIDSYNTH_MISSING} ({exc})") from exc
        if completed.returncode != 0:
            wav.unlink(missing_ok=True)
            detail = _fluidsynth_detail(completed.stderr, completed.stdout)
            message = f"fluidsynth failed (exit {completed.returncode}) rendering {midi}"
            if detail:
                message = f"{message}: {detail}"
            raise RenderError(message)
        try:
            duration, size_bytes = _wav_stats(wav)
        except RenderError:
            wav.unlink(missing_ok=True)
            raise
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    return RenderedWav(wav, font, duration, size_bytes)
