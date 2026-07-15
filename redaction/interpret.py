"""Tag Latin-alphabet language switches with the LLM — the interpretation of tongues.

The deterministic tagger reads writing systems, so within the Latin alphabet
it is blind: Couliano's French, a Latin quotation, an Italian title all pass
for English. "To another, the interpretation of tongues" (1 Cor 12:10) —
this layer asks a model to name each foreign stretch so the reciter can
pronounce it in its own language.

Tagging is maximal by design: not only quotations and titles but naturalised
loanwords, Latin phrases, transliterated Greek terms of art, and proper
names — anglicised pronunciation of any of them impedes the listener this
pipeline is built for. The model returns only verbatim substrings with a
language code (tiny outputs — tokens are the expensive part); the splitting
happens here, so a substring that cannot be found verbatim is simply
discarded rather than trusted.
"""

import hashlib
import json
import re
from collections.abc import Callable, Iterator
from pathlib import Path

from pydantic import BaseModel

from redaction.base import Script, ScriptSection, Utterance
from redaction.providers import Provider

_SYSTEM = """\
You are preparing a scholarly monograph (religious studies) for audio narration \
by a reader who speaks the languages the book quotes. You receive numbered \
stretches of running text. Find every stretch that is not English and should be \
pronounced in its own language, and return it as a verbatim substring — copied \
exactly, punctuation and all — with the number of the stretch it appears in and \
its language code.

Tag maximally. This includes:
- quotations, verse, mottoes, and epigraphs in other languages
- titles of works (Latin, French, German, Italian, ...)
- Latin and French phrases however naturalised (per se, a priori, par excellence)
- transliterated Greek or Hebrew terms of art (goetes -> grc, torah -> he)
- proper names whose written form is the source-language form (Peregrinus -> la, \
Dionysius of Halicarnassus -> la); anglicised forms are English words and stay \
untagged (Aristotle, Rome, Pliny)

Do not tag English words, and do not paraphrase: every returned text must be a \
character-exact copy from the stretch it points to.

Language codes: ISO 639 (la, fr, it, de, es, grc for ancient Greek, he, arc for \
Aramaic, ar). Use grc, not el, for anything from the ancient world.\
"""

_BATCH_CHARS = 3500  # keep requests small and cache-friendly


class Switch(BaseModel):
    stretch: int
    text: str
    lang: str


class Switches(BaseModel):
    switches: list[Switch]


class TongueInterpreter:
    """LLM counterpart to the deterministic LanguageTagger."""

    def __init__(
        self,
        provider: Provider,
        cache_path: Path | None = None,
        log: Callable[[str], None] = lambda message: None,
    ) -> None:
        self.provider = provider
        self._cache_path = cache_path
        self._cache: dict[str, list[dict]] = {}
        if cache_path is not None and cache_path.exists():
            self._cache = json.loads(cache_path.read_text())
        self._log = log

    def redact(self, script: Script) -> Script:
        return Script(sections=[self._interpret_section(s) for s in script.sections])

    def _interpret_section(self, section: ScriptSection) -> ScriptSection:
        english = [u for u in section.utterances if u.lang == "en"]
        switches: dict[int, list[Switch]] = {}
        for batch in _batches(english):
            for index, found in self._ask(batch).items():
                switches.setdefault(id(batch[index]), []).extend(found)
        tagged = sum(len(v) for v in switches.values())
        if tagged:
            self._log(f"interpreting '{section.title}': {tagged} switches")
        utterances: list[Utterance] = []
        for utterance in section.utterances:
            utterances.extend(_split(utterance, switches.get(id(utterance), [])))
        return ScriptSection(
            title=section.title, utterances=utterances, footnotes=section.footnotes
        )

    def _ask(self, batch: list[Utterance]) -> dict[int, list[Switch]]:
        request = "\n\n".join(f"[{i}] {u.text}" for i, u in enumerate(batch))
        key = hashlib.sha256(f"{self.provider.label}\0{request}".encode()).hexdigest()
        raw = self._cache.get(key)
        if raw is None:
            answer = self.provider.ask(_SYSTEM, request, Switches)
            if answer is None:
                return {}
            raw = [s.model_dump() for s in answer.switches]
            self._cache[key] = raw
            if self._cache_path is not None:
                self._cache_path.write_text(json.dumps(self._cache, ensure_ascii=False, indent=1))
        result: dict[int, list[Switch]] = {}
        for entry in raw:
            switch = Switch(**entry)
            if 0 <= switch.stretch < len(batch):
                result.setdefault(switch.stretch, []).append(switch)
        return result


def _batches(utterances: list[Utterance], budget: int = _BATCH_CHARS) -> Iterator[list[Utterance]]:
    batch: list[Utterance] = []
    size = 0
    for utterance in utterances:
        if batch and size + len(utterance.text) > budget:
            yield batch
            batch, size = [], 0
        batch.append(utterance)
        size += len(utterance.text)
    if batch:
        yield batch


def _split(utterance: Utterance, switches: list[Switch]) -> list[Utterance]:
    """Carve the tagged stretches out of the utterance, in text order.

    A switch that cannot be located verbatim (whitespace aside) is dropped:
    the model's word is never trusted over the author's text.
    """
    located: list[tuple[int, int, str]] = []
    taken: list[tuple[int, int]] = []
    for switch in switches:
        span = _locate(utterance.text, switch.text)
        if span is None or any(s < span[1] and span[0] < e for s, e in taken):
            continue
        located.append((*span, switch.lang.lower()))
        taken.append((span[0], span[1]))
    if not located:
        return [utterance]
    pieces: list[Utterance] = []
    consumed = 0
    for start, end, lang in sorted(located):
        if before := utterance.text[consumed:start].strip():
            pieces.append(Utterance(text=before, manner=utterance.manner, lang=utterance.lang))
        pieces.append(Utterance(text=utterance.text[start:end], manner=utterance.manner, lang=lang))
        consumed = end
    if after := utterance.text[consumed:].strip():
        pieces.append(Utterance(text=after, manner=utterance.manner, lang=utterance.lang))
    return pieces


def _locate(text: str, needle: str) -> tuple[int, int] | None:
    start = text.find(needle)
    if start != -1:
        return start, start + len(needle)
    # whitespace-tolerant second try
    pattern = r"\s+".join(re.escape(word) for word in needle.split())
    match = re.search(pattern, text)
    return (match.start(), match.end()) if match else None
