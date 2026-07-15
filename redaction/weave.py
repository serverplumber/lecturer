"""Weave footnotes into the running text as spoken digressions.

The deterministic baseline: each note is spoken, verbatim, where the
sentence carrying its anchor ends, and the ``[^ref]`` markers disappear
from the body text. The planned LLM layer will instead judge which notes
deserve airtime and rephrase them as asides; until then every note is
read as written. Notes whose anchor never appears stay on the section's
``footnotes`` list so nothing is silently dropped.
"""

import re

from extraction import Footnote
from redaction.base import ANCHOR, Manner, Script, ScriptSection, Utterance

# The curly closing quotes are intentional: typeset books use them.
_SENTENCE_END = re.compile(r"[.!?…][)\]\"'”’]*(?=\s|$)")  # noqa: RUF001
_ENDS_SENTENCE = re.compile(r"[.!?…][)\]\"'”’]*$")  # noqa: RUF001


class FootnoteWeaver:
    def redact(self, script: Script) -> Script:
        return Script(sections=[_weave_section(section) for section in script.sections])


def _weave_section(section: ScriptSection) -> ScriptSection:
    notes = {note.ref: note for note in section.footnotes}
    woven: set[str] = set()
    utterances: list[Utterance] = []
    for utterance in section.utterances:
        if utterance.manner is Manner.BODY:
            utterances.extend(weave_utterance(utterance, notes, woven))
        else:
            utterances.append(utterance)
    leftovers = [note for ref, note in notes.items() if ref not in woven]
    return ScriptSection(title=section.title, utterances=utterances, footnotes=leftovers)


def weave_utterance(
    utterance: Utterance, notes: dict[str, Footnote], woven: set[str]
) -> list[Utterance]:
    """Split one body utterance around its anchors' sentence ends.

    The anchors are stripped from the text first; each ref remembers its
    position in the stripped text, then attaches to the end of the sentence
    it sat in (anchors placed right after the full stop attach to that
    sentence, not the next). Multiple notes at one break are spoken in order.
    """
    stripped_parts: list[str] = []
    positions: list[tuple[int, str]] = []
    consumed = 0
    length = 0
    for match in ANCHOR.finditer(utterance.text):
        stripped_parts.append(utterance.text[consumed : match.start()])
        length += match.start() - consumed
        positions.append((length, match.group(1)))
        consumed = match.end()
    if not positions:
        return [utterance]
    stripped_parts.append(utterance.text[consumed:])
    stripped = "".join(stripped_parts)

    breaks: dict[int, list[str]] = {}
    for position, ref in positions:
        if _ENDS_SENTENCE.search(stripped, 0, position):
            cut = position
        else:
            ahead = _SENTENCE_END.search(stripped, position)
            cut = ahead.end() if ahead else len(stripped)
        breaks.setdefault(cut, []).append(ref)

    result: list[Utterance] = []
    start = 0
    for cut in sorted(breaks):
        if body := stripped[start:cut].strip():
            result.append(Utterance(text=body, manner=Manner.BODY))
        for ref in breaks[cut]:
            if note := notes.get(ref):
                woven.add(ref)
                result.append(Utterance(text=note.text, manner=Manner.DIGRESSION))
        start = cut
    if tail := stripped[start:].strip():
        result.append(Utterance(text=tail, manner=Manner.BODY))
    return result
