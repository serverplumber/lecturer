"""Recite the redacted script aloud — the pipeline's final stage.

A ``Reciter`` turns one utterance into audio samples (or declines it, e.g.
a language the voice cannot speak); ``recite`` walks the script, breathes
between utterances, and writes one WAV per section into ``audio/``.
"""

import hashlib
import json
import re
from collections.abc import Callable
from pathlib import Path
from typing import Protocol

import numpy as np
import soundfile

from recitation.kokoro import KokoroReciter
from recitation.lexicon import Lexicon, draft
from redaction import Manner, Script, Utterance

__all__ = ["APPARATUS", "KokoroReciter", "Lexicon", "Reciter", "draft", "publish", "recite"]

# Sections that are scholarly apparatus, not lecture: nobody wants ninety
# minutes of impeccably pronounced bibliography. The CLI skips titles
# matching this by default; --sections overrides.
APPARATUS = re.compile(
    r"front matter|bibliograph|index|contents|acknowledg|abbreviation|"
    r"list of (figures|tables|illustrations|maps)|copyright|^notes?$",
    re.IGNORECASE,
)

# Breathing room between utterances, in seconds: a paragraph break gets a
# proper pause, the pivot into or out of an aside a shorter one.
_PARAGRAPH_PAUSE = 0.6
_DIGRESSION_PAUSE = 0.35


class Reciter(Protocol):
    """Strategy interface — one implementation per TTS engine."""

    sample_rate: int
    fingerprint: str  # engine + settings; part of each section's signature

    def utter(self, utterance: Utterance) -> np.ndarray | None: ...


def recite(
    script: Script,
    directory: Path,
    reciter: Reciter,
    stem: Callable[[int, str], str],
    log: Callable[[str], None] = lambda message: None,
    skip: Callable[[str], bool] = lambda title: False,
    variant: str = "book",
) -> Path:
    """Write each section to ``audio/<variant>/NN_title.wav``.

    ``skip`` is asked per section title; skipped sections keep their index,
    so filenames always match ``sections/`` and ``redactions/`` regardless
    of what is spoken.

    Weaving variants are forks, not successors: the plain ``book`` and the
    footnote-woven ``glossed`` renderings live side by side, each in its
    own directory. Within a variant, each WAV carries a sidecar ``.sig``
    naming the reciter and hashing the section's utterances — a re-run
    keeps what is unchanged and overwrites what a new script, voice, or
    speed has made stale.
    """
    audio_dir = directory / "audio" / variant
    audio_dir.mkdir(parents=True, exist_ok=True)
    for index, section in enumerate(script.sections, start=1):
        if skip(section.title):
            log(f"skipping '{section.title}' (apparatus; --sections overrides)")
            continue
        path = audio_dir / f"{stem(index, section.title)}.wav"
        sig_path = path.with_suffix(".sig")
        signature = _signature(section, reciter)
        if path.exists() and path.stat().st_size > 0 and _stamped(sig_path) == signature:
            log(f"kept '{section.title}' (unchanged)")
            continue
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
        soundfile.write(path, samples, reciter.sample_rate, subtype="PCM_16")
        sig_path.write_text(
            json.dumps({"reciter": reciter.fingerprint, "sha256": signature}, indent=1)
        )
        log(f"recited '{section.title}': {len(samples) / reciter.sample_rate / 60:.1f} minutes")
    return audio_dir


def _stamped(sig_path: Path) -> str | None:
    """The signature recorded beside a WAV, or ``None`` if absent/unreadable."""
    try:
        return json.loads(sig_path.read_text())["sha256"]
    except (OSError, ValueError, KeyError):
        return None


def _signature(section, reciter: Reciter) -> str:
    # Reciters with a lexicon contribute the digest of the entries this
    # section actually uses: editing an entry re-renders only its sections.
    pointing = getattr(reciter, "lexicon_digest", None)
    lexicon = pointing(" ".join(u.text for u in section.utterances)) if pointing else ""
    payload = json.dumps(
        [reciter.fingerprint, lexicon, *((u.text, u.manner, u.lang) for u in section.utterances)]
    )
    return hashlib.sha256(payload.encode()).hexdigest()


def _pause(before: Utterance, after: Utterance, sample_rate: int) -> np.ndarray:
    aside = Manner.DIGRESSION in (before.manner, after.manner)
    seconds = _DIGRESSION_PAUSE if aside else _PARAGRAPH_PAUSE
    return np.zeros(int(seconds * sample_rate), dtype=np.float32)


def publish(
    script: Script,
    directory: Path,
    stem: Callable[[int, str], str],
    log: Callable[[str], None] = lambda message: None,
    skip: Callable[[str], bool] = lambda title: False,
    variant: str = "book",
) -> Path | None:
    """Bind the recited sections: WAVs become Opus, plus an M3U playlist.

    Opus is transparent at speech bitrates and roughly a tenth of the WAV
    size; the playlist carries section titles and durations, in reading
    order. Conversion streams block-wise (a ninety-minute WAV must never
    sit in memory) and is skipped when the Opus is already newer than its
    WAV. Returns the playlist path, or ``None`` if nothing was published.
    """
    audio_dir = directory / "audio" / variant
    entries: list[tuple[str, float, str]] = []
    reciters: set[str] = set()
    for index, section in enumerate(script.sections, start=1):
        if skip(section.title):
            continue
        wav = audio_dir / f"{stem(index, section.title)}.wav"
        if not wav.exists():
            continue
        opus = wav.with_suffix(".opus")
        if not opus.exists() or opus.stat().st_mtime < wav.stat().st_mtime:
            _convert(wav, opus)
            log(
                f"bound '{section.title}': "
                f"{wav.stat().st_size >> 20} MB wav -> {opus.stat().st_size >> 20} MB opus"
            )
        entries.append((opus.name, soundfile.info(wav).duration, section.title))
        if reciter := _reciter_of(wav.with_suffix(".sig")):
            reciters.add(reciter)
    if not entries:
        return None
    playlist = audio_dir / f"{directory.resolve().name}_{variant}.m3u"
    lines = ["#EXTM3U"]
    lines += [f"# reciter: {reciter}" for reciter in sorted(reciters)]
    for name, duration, title in entries:
        lines += [f"#EXTINF:{round(duration)},{title}", name]
    playlist.write_text("\n".join(lines) + "\n")
    return playlist


def _reciter_of(sig_path: Path) -> str | None:
    try:
        return json.loads(sig_path.read_text())["reciter"]
    except (OSError, ValueError, KeyError):
        return None


def _convert(wav: Path, opus: Path) -> None:
    partial = opus.with_suffix(".opus.part")
    with (
        soundfile.SoundFile(wav) as source,
        soundfile.SoundFile(
            partial,
            "w",
            samplerate=source.samplerate,
            channels=source.channels,
            format="OGG",
            subtype="OPUS",
        ) as sink,
    ):
        while True:
            block = source.read(1 << 20, dtype="float32")
            if not len(block):
                break
            sink.write(block)
    partial.rename(opus)
