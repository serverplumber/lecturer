"""Recite the redacted script aloud — the pipeline's final stage.

A ``Reciter`` turns one utterance into audio samples (or declines it, e.g.
a language the voice cannot speak); ``recite`` walks the script, breathes
between utterances, and writes one WAV per section into ``audio/``.
"""

from collections.abc import Callable
from pathlib import Path
from typing import Protocol

import numpy as np
import soundfile

from recitation.kokoro import KokoroReciter
from redaction import Manner, Script, Utterance

__all__ = ["KokoroReciter", "Reciter", "recite"]

# Breathing room between utterances, in seconds: a paragraph break gets a
# proper pause, the pivot into or out of an aside a shorter one.
_PARAGRAPH_PAUSE = 0.6
_DIGRESSION_PAUSE = 0.35


class Reciter(Protocol):
    """Strategy interface — one implementation per TTS engine."""

    sample_rate: int

    def utter(self, utterance: Utterance) -> np.ndarray | None: ...


def recite(
    script: Script,
    directory: Path,
    reciter: Reciter,
    stem: Callable[[int, str], str],
    log: Callable[[str], None] = lambda message: None,
) -> Path:
    """Write each section to ``audio/NN_title.wav``; returns the directory."""
    audio_dir = directory / "audio"
    audio_dir.mkdir(exist_ok=True)
    for index, section in enumerate(script.sections, start=1):
        pieces: list[np.ndarray] = []
        previous: Utterance | None = None
        for utterance in section.utterances:
            audio = reciter.utter(utterance)
            if audio is None:
                continue
            if previous is not None:
                pieces.append(_pause(previous, utterance, reciter.sample_rate))
            pieces.append(audio)
            previous = utterance
        if not pieces:
            continue
        samples = np.concatenate(pieces)
        path = audio_dir / f"{stem(index, section.title)}.wav"
        soundfile.write(path, samples, reciter.sample_rate, subtype="PCM_16")
        log(f"recited '{section.title}': {len(samples) / reciter.sample_rate / 60:.1f} minutes")
    return audio_dir


def _pause(before: Utterance, after: Utterance, sample_rate: int) -> np.ndarray:
    aside = Manner.DIGRESSION in (before.manner, after.manner)
    seconds = _DIGRESSION_PAUSE if aside else _PARAGRAPH_PAUSE
    return np.zeros(int(seconds * sample_rate), dtype=np.float32)
