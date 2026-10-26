from __future__ import annotations

import math, wave
from pathlib import Path
import numpy as np
from .models import HummedNote, Note


def _midi(freq: float) -> int: return int(round(69 + 12 * math.log2(freq / 440)))


def transcribe_wav(path: str | Path) -> list[HummedNote]:
    with wave.open(str(path), "rb") as w:
        rate, channels, width = w.getframerate(), w.getnchannels(), w.getsampwidth(); raw = w.readframes(w.getnframes())
    if width != 2: raise ValueError("v1 humming input must be 16-bit PCM WAV")
    audio = np.frombuffer(raw, dtype=np.int16).astype(float)
    if channels > 1: audio = audio.reshape(-1, channels).mean(axis=1)
    frame = max(512, int(rate * .05)); hop = frame // 2; found = []
    for i in range(0, len(audio)-frame, hop):
        x = audio[i:i+frame]; rms = np.sqrt(np.mean(x*x))
        if rms < 300: continue
        corr = np.correlate(x, x, mode="full")[len(x)-1:]
        zero_lag = float(corr[0])
        corr[:int(rate/1000)] = 0
        lag = int(np.argmax(corr[:int(rate/60)]));
        if lag <= 0: continue
        confidence = float(np.clip(corr[lag] / max(zero_lag, 1), 0, 1))
        freq = rate / lag
        if 70 <= freq <= 1000: found.append((i/rate, freq, confidence))
    notes=[]
    for start, freq, conf in found:
        pitch=_midi(freq)
        # A 50 ms frame with 50% overlap produces ~25 ms hops on most files;
        # merge same-pitch frames across a short gap into one musical note.
        if notes and notes[-1].note.pitch == pitch and start - notes[-1].note.start < .35:
            old=notes[-1]; notes[-1]=HummedNote(note=old.note.model_copy(update={"duration": start-old.note.start+.05}), frequency_hz=freq, confidence=max(old.confidence,conf), needs_review=old.confidence<.7)
        else:
            notes.append(HummedNote(note=Note(pitch=pitch,start=start,duration=.1,velocity=96,confidence=conf), frequency_hz=freq, confidence=conf, needs_review=conf<.7))
    return notes
