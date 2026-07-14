"""Mend paragraphs torn apart by page breaks.

Extraction emits paragraphs block by block, so a paragraph interrupted by
a page turn (often with a footnote block wedged in between) arrives as two
fragments. The papyrologists' term for fitting such fragments back together
is a join, and the signals are deterministic: a fragment that opens in
lowercase continues its neighbour, and one that stops mid-sentence wants
the next fragment — unless it is a heading, which ends where it ends.
Lowercase is checked per Unicode, so Greek and friends join too.

This layer must run before the footnote weaver: it reasons about paragraph
seams, which weaving (splitting at sentence ends, inserting digressions)
would destroy.
"""

import re

from redaction.base import ANCHOR, Manner, Script, ScriptSection, Utterance

# Anything a finished paragraph may end on: sentence-final punctuation or a
# colon introducing a block quote, plus closing quotes and brackets. The
# curly closing quotes are intentional: typeset books use them.
_ENDS_PARAGRAPH = re.compile(r"[.!?…:][)\]\"'”’]*$")  # noqa: RUF001
_WORD = re.compile(r"[^\W\d_]+")
_HEADING_MAX_CHARS = 80


class SeamMender:
    def redact(self, script: Script) -> Script:
        return Script(sections=[_mend_section(section) for section in script.sections])


def _mend_section(section: ScriptSection) -> ScriptSection:
    utterances: list[Utterance] = []
    for utterance in section.utterances:
        previous = utterances[-1] if utterances else None
        if (
            previous is not None
            and previous.manner is Manner.BODY
            and utterance.manner is Manner.BODY
            and _joins(previous.text, utterance.text)
        ):
            utterances[-1] = Utterance(text=_join(previous.text, utterance.text))
        else:
            utterances.append(utterance)
    return ScriptSection(title=section.title, utterances=utterances, footnotes=section.footnotes)


def _joins(previous: str, following: str) -> bool:
    """True if ``following`` is the torn-off continuation of ``previous``.

    Anchors are ignored for the boundary test: a fragment ending in
    ``word[^ref]`` still ends on ``word``.
    """
    if _first_letter(following).islower():
        return True
    bare = ANCHOR.sub("", previous).rstrip()
    return not _ENDS_PARAGRAPH.search(bare) and not _heading_like(bare)


def _join(previous: str, following: str) -> str:
    if previous.endswith("-") and _first_letter(following).islower():
        return previous[:-1] + following
    return f"{previous} {following}"


def _first_letter(text: str) -> str:
    return next((char for char in ANCHOR.sub("", text) if char.isalpha()), "")


def _heading_like(text: str) -> bool:
    """Short fragments with mostly capitalised words read as headings."""
    if len(text) > _HEADING_MAX_CHARS:
        return False
    words = _WORD.findall(text)
    if not words:
        return True
    return sum(word[0].isupper() for word in words) >= len(words) / 2
