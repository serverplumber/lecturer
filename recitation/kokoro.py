"""Kokoro TTS through ONNX runtime — 82M parameters, faster than realtime on CPU.

The model and voice files are fetched once into the user cache. Kokoro
speaks from a fixed catalogue of voices (no cloning); the voice's prefix
decides the English flavour (``af_``/``am_`` American, ``bf_``/``bm_``
British). Not every voice can read this prose: af_heart and af_bella
insert loud glottal pauses before vowel-initial words ("freelance —
experts"); af_aoede, af_jessica, af_kore, and af_river measured clean.

Utterances tagged with languages the voice cannot speak (the tagger's
``grc``, ``he``, …) are declined and counted in ``skipped`` — until a
transliteration or multilingual engine exists, those stretches stay
silent.
"""

import os
import re
import urllib.request
from collections import Counter
from collections.abc import Callable, Iterator
from pathlib import Path

import numpy as np
from kokoro_onnx import SAMPLE_RATE, Kokoro

from redaction import Utterance

_RELEASE = "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0"
_MODEL = "kokoro-v1.0.onnx"
_VOICES = "voices-v1.0.bin"

# Languages Kokoro can actually speak, with the espeak code and the voice
# that carries each: a tagged utterance in one of these switches voice
# mid-lecture; anything else (grc, he, ar, ...) is skipped and counted.
_TONGUES = {
    "it": ("it", "if_sara"),
    "fr": ("fr-fr", "ff_siwis"),
    "es": ("es", "ef_dora"),
    "pt": ("pt-br", "pf_dora"),
    "hi": ("hi", "hf_alpha"),
}

# Kokoro synthesises at most 510 phonemes at a go; fed more, kokoro-onnx
# splices batches at arbitrary word gaps, which lands mid-sentence in long
# academic paragraphs and sounds like randomly sprinkled commas. We chunk at
# sentence boundaries well under the limit instead (phonemes run ≈1.04 per
# character on this corpus) and rejoin with a natural sentence gap.
_CHUNK_CHARS = 380
_CHUNK_GAP = 0.2  # seconds
_SENTENCE = re.compile(r"[^.!?…]*(?:[.!?…]+[)\]\"'”’]*\s*|$)")  # noqa: RUF001
_CLAUSE = re.compile(r"[^,;:]*(?:[,;:]\s*|$)")


class KokoroReciter:
    sample_rate = SAMPLE_RATE

    def __init__(
        self,
        voice: str = "af_kore+af_aoede",
        speed: float = 1.0,
        cache_dir: Path | None = None,
        log: Callable[[str], None] = lambda message: None,
    ) -> None:
        cache = cache_dir or _default_cache()
        model = _fetch(f"{_RELEASE}/{_MODEL}", cache / _MODEL, log)
        voices = _fetch(f"{_RELEASE}/{_VOICES}", cache / _VOICES, log)
        self._kokoro = Kokoro(str(model), str(voices))
        self._voice = self._style(voice)
        self._speed = speed
        self._lang = "en-gb" if voice.startswith("b") else "en-us"
        self.skipped: Counter[str] = Counter()

    def _style(self, voice: str) -> str | np.ndarray:
        """Resolve a voice name, or blend ``af_kore+af_aoede`` into one style.

        Voices are style vectors, so a mix is their weighted mean; weight
        with ``af_kore:2+af_aoede:1``, unweighted parts count once.
        """
        if "+" not in voice:
            return voice
        blend = None
        total = 0.0
        for part in voice.split("+"):
            name, _, weight = part.partition(":")
            factor = float(weight) if weight else 1.0
            style = self._kokoro.get_voice_style(name.strip()) * factor
            blend = style if blend is None else blend + style
            total += factor
        return (blend / total).astype(np.float32)

    def utter(self, utterance: Utterance) -> np.ndarray | None:
        if utterance.lang == "en":
            lang, voice = self._lang, self._voice
        elif utterance.lang in _TONGUES:
            lang, voice = _TONGUES[utterance.lang]
        else:
            self.skipped[utterance.lang] += 1
            return None
        gap = np.zeros(int(_CHUNK_GAP * self.sample_rate), dtype=np.float32)
        pieces: list[np.ndarray] = []
        for chunk in _chunks(utterance.text):
            samples, _rate = self._kokoro.create(chunk, voice=voice, speed=self._speed, lang=lang)
            if pieces:
                pieces.append(gap)
            pieces.append(samples)
        return np.concatenate(pieces) if pieces else None


def _chunks(text: str, budget: int = _CHUNK_CHARS) -> Iterator[str]:
    """Split ``text`` into synthesis chunks that end at sentence boundaries.

    Sentences pack greedily up to the budget; a single sentence that
    overflows it on its own (this corpus has 500-character sentences) is
    packed the same way at clause punctuation, so any remaining splice
    falls where a pause belongs anyway.
    """
    current = ""
    for sentence in _SENTENCE.findall(text):
        if not sentence.strip():
            continue
        for part in _pack(sentence, budget):
            if current and len(current) + len(part) > budget:
                yield current.strip()
                current = part
            else:
                current += part
    if current.strip():
        yield current.strip()


def _pack(sentence: str, budget: int) -> Iterator[str]:
    if len(sentence) <= budget:
        yield sentence
        return
    current = ""
    for clause in _CLAUSE.findall(sentence):
        if current and len(current) + len(clause) > budget:
            yield current
            current = clause
        else:
            current += clause
    if current:
        yield current


def _default_cache() -> Path:
    base = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache"))
    return base / "lecturer"


def _fetch(url: str, path: Path, log: Callable[[str], None]) -> Path:
    """Download ``url`` to ``path`` once, atomically."""
    if path.exists():
        return path
    path.parent.mkdir(parents=True, exist_ok=True)
    log(f"fetching {path.name} ...")
    partial = path.with_suffix(path.suffix + ".part")
    urllib.request.urlretrieve(url, partial)
    partial.rename(path)
    return path
