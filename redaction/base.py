"""Core types for the redactional layers.

The name means what it looks like: redaction criticism studies how editors
wove their sources into a single running text, and that is this module's
job — rework the extracted text and its footnotes, layer by layer, into a
script fit to be read aloud. Each layer is a ``Redactor``; the layers are
applied in order and each leaves the script closer to performable.
"""

import re
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Protocol, Self

from extraction import Extraction, Footnote

# A footnote anchor as extraction leaves it in the running text, with any
# whitespace the typesetting put before it.
ANCHOR = re.compile(r"\s*\[\^([^\]]+)\]")


class Manner(StrEnum):
    """How a stretch of the script is delivered."""

    BODY = "body"
    DIGRESSION = "digression"


@dataclass
class Utterance:
    """A stretch of the script delivered in one manner."""

    text: str
    manner: Manner = Manner.BODY


@dataclass
class ScriptSection:
    """One section of the script, mirroring the extraction's sections.

    ``footnotes`` holds the notes not yet woven into the utterances; a
    finished script has none left.
    """

    title: str
    utterances: list[Utterance]
    footnotes: list[Footnote] = field(default_factory=list)


@dataclass
class Script:
    """The lecture script the TTS will eventually perform."""

    sections: list[ScriptSection]

    @classmethod
    def from_extraction(cls, extraction: Extraction) -> Self:
        """The unredacted starting point: one body utterance per paragraph."""
        return cls(
            sections=[
                ScriptSection(
                    title=section.title,
                    utterances=[
                        Utterance(text=paragraph)
                        for paragraph in section.text.split("\n\n")
                        if paragraph.strip()
                    ],
                    footnotes=list(section.footnotes),
                )
                for section in extraction.sections
            ]
        )


class Redactor(Protocol):
    """One redactional layer, reworking the whole script."""

    def redact(self, script: Script) -> Script: ...
