"""Core types for the extraction strategies."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol


@dataclass
class Footnote:
    """A footnote lifted out of the running text.

    ``ref`` is the note's identifier in the source document; the running
    text carries a matching ``[^ref]`` marker where the note was anchored.
    """

    ref: str
    text: str


@dataclass
class Section:
    """One division of the book — chapter, introduction, front matter lump."""

    title: str
    text: str
    footnotes: list[Footnote] = field(default_factory=list)


@dataclass
class Extraction:
    """What an extractor produces: the book's sections in reading order."""

    sections: list[Section]

    @property
    def text(self) -> str:
        return "\n\n".join(section.text for section in self.sections if section.text)

    @property
    def footnotes(self) -> list[Footnote]:
        return [note for section in self.sections for note in section.footnotes]


class Extractor(Protocol):
    """Strategy interface — one implementation per document format."""

    def extract(self, document: Path) -> Extraction: ...


class UnsupportedFormatError(Exception):
    def __init__(self, suffix: str) -> None:
        super().__init__(f"no extractor for {suffix or 'files without a suffix'}")
        self.suffix = suffix
