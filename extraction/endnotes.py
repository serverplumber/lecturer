"""Heuristic fallback for books whose notes live in a plain endnotes chapter.

Scanned or converted books (calibre productions especially) often carry no
semantic footnote markup at all: note anchors are bare superscript numbers
and the notes sit in a chapter headed "Notes", grouped under section labels
like "Introduction" or "Chapter 4". This module parses that chapter and
pairs each ``<sup>`` anchor with its note by (section, number).
"""

import re

from bs4 import BeautifulSoup

from extraction.base import Footnote

_NOTES_HEADING = re.compile(r"^(?:end)?notes$", re.IGNORECASE)
_NOTE_START = re.compile(r"^(\d+)\.?\s+(.*)", re.DOTALL)
_CHAPTER_LABEL = re.compile(r"^(?:notes\s+to\s+)?chapter\s+(\d+)$", re.IGNORECASE)
_NUMBERED_HEADING = re.compile(r"^(\d+)\b")
_FRONT_SECTIONS = frozenset(
    {"introduction", "foreword", "preface", "prologue", "epilogue", "conclusion", "afterword"}
)


def pull_endnotes(soups: list[BeautifulSoup]) -> list[Footnote]:
    """Extract endnotes from the chapters and mark their anchors in the text.

    Notes chapters are emptied (their content returns as ``Footnote``s), and
    each matched superscript anchor is replaced by the ``[^ref]`` marker of
    its note. Chapters are expected in spine order so that split chapter
    files inherit the section of the preceding heading.
    """
    notes: dict[tuple[str, str], Footnote] = {}
    for soup in soups:
        if _is_notes_chapter(soup):
            _parse_notes_chapter(soup, notes)
            soup.body.clear()
    if not notes:
        return []

    section = None
    for soup in soups:
        section = _body_section(soup, previous=section)
        for sup in soup.find_all("sup"):
            number = sup.get_text(strip=True)
            note = notes.get((section, number))
            if note is not None:
                sup.replace_with(f"[^{note.ref}]")
    return list(notes.values())


def _is_notes_chapter(soup: BeautifulSoup) -> bool:
    heading = soup.find(["h1", "h2", "h3"])
    return heading is not None and bool(_NOTES_HEADING.match(heading.get_text(" ", strip=True)))


def _parse_notes_chapter(soup: BeautifulSoup, notes: dict[tuple[str, str], Footnote]) -> None:
    """Walk the chapter's paragraphs: section labels, note starts, continuations."""
    section = None
    current = None
    for paragraph in soup.find_all("p"):
        text = paragraph.get_text(" ", strip=True)
        if not text:
            continue
        if (label := _section_label(text)) is not None:
            section = label
            current = None
        elif (start := _NOTE_START.match(text)) and section is not None:
            number, body = start.groups()
            current = Footnote(ref=f"{section}-n{number}", text=body)
            notes[(section, number)] = current
        elif current is not None:
            current.text += "\n" + text


def _section_label(text: str) -> str | None:
    """Normalize a section label paragraph, e.g. "Chapter 4" -> "chapter-4"."""
    if match := _CHAPTER_LABEL.match(text):
        return f"chapter-{match.group(1)}"
    if text.lower() in _FRONT_SECTIONS:
        return text.lower()
    return None


def _body_section(soup: BeautifulSoup, previous: str | None) -> str | None:
    """Infer which notes section a chapter's anchors belong to from its heading.

    Chapter headings look like "6| Intersubjective Magic" or "Introduction";
    a file with no recognizable heading (e.g. the tail of a split chapter)
    stays in the previous section.
    """
    heading = soup.find(["h1", "h2", "h3"])
    if heading is None:
        return previous
    text = heading.get_text(" ", strip=True)
    if match := _NUMBERED_HEADING.match(text):
        return f"chapter-{match.group(1)}"
    if text.lower() in _FRONT_SECTIONS:
        return text.lower()
    return previous
