"""PDF extraction.

Relies on the PDF's embedded text layer — for scanned books, whatever OCR
the producer ran. Text is read block by block; running heads and page
numbers (short blocks whose normalized text repeats across many pages) are
dropped and hyphenation across line breaks is repaired.

Born-digital books typeset their footnotes in a smaller face at the foot
of the page, with superscript anchors in the body. When the document's
font profile shows such a second, smaller text size, those blocks are
parsed into footnotes and the anchors become ``[^ref]`` markers. Scanned
books have no such profile (OCR flattens it), so they fall back to text
only.
"""

import itertools
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

import pymupdf

from extraction.base import Extraction, Footnote, Section

_PAGE_NUMBER = re.compile(r"^(?:\d+|[ivxlcdm]+)$", re.IGNORECASE)
_HYPHEN_BREAK = re.compile(r"-\n(?=[a-z])")
_SOFT_HYPHEN = re.compile(r"­\s*")
# C0 controls and DEL, except tab and newline: text layers hide artefacts
# like backspace between a running head and its page number.
_CONTROL = re.compile(r"[\x00-\x08\x0b-\x1f\x7f]")
_NOTE_START = re.compile(r"^(\d+)\.\s+(.*)", re.DOTALL)
_FURNITURE_MAX_CHARS = 80
# A short block recurring as the first or last block of a page (running
# head, running foot) is furniture even when a short chapter keeps its
# total count below the global threshold.
_EDGE_THRESHOLD = 3
_SUPERSCRIPT_FLAG = 1
# How much larger than the body face a block must be set to read as a heading.
_HEADING_MARGIN = 1.0


@dataclass
class _Span:
    text: str
    size: float
    superscript: bool


class PdfExtractor:
    def extract(self, document: Path) -> Extraction:
        with pymupdf.open(document) as doc:
            pages = [_page_blocks(page) for page in doc]
            outline = doc.get_toc()

        body_size, note_size = _font_profile(pages)
        furniture = _furniture(pages)
        page_texts, notes = _assemble(pages, body_size, note_size, furniture)
        # Footnote mode only holds if the superscript anchors in the body
        # actually pair with the parsed notes. On scanned books the pairing
        # collapses (OCR font jitter, no real anchors) and the "notes" are
        # torn-out running text — re-extract with footnote mode off.
        if notes and not _pairing_holds(page_texts, notes):
            page_texts, notes = _assemble(pages, body_size, None, furniture)
        return Extraction(sections=_split_sections(page_texts, notes, outline))


def _assemble(
    pages: list[list[list[list[_Span]]]],
    body_size: float,
    note_size: float | None,
    furniture: set[str],
) -> tuple[list[list[str]], list[tuple[int, Footnote]]]:
    """Extract every page: its body paragraphs, and (page, footnote) pairs."""
    page_texts: list[list[str]] = []
    notes: list[tuple[int, Footnote]] = []
    for page_number, blocks in enumerate(pages, start=1):
        paragraphs: list[str] = []
        # Heading-sized blocks are never furniture: a chapter heading often
        # repeats verbatim as the running head of its own pages, and only
        # the small-face copies should be dropped.
        content = [
            b
            for b in blocks
            if _is_heading(b, body_size) or not _is_page_furniture(_plain_text(b), furniture)
        ]
        content = _merge_wrapped_headings(content, body_size)
        note_flags = [_is_note_block(b, body_size, note_size) for b in content]
        # A page with nothing body-sized is not a footnote page: it is
        # front or back matter set in a small face (bibliographies
        # especially), which would otherwise parse as phantom notes.
        # Headings don't count as body here — a bibliography's own title
        # must not turn its entries into notes.
        if all(
            flag
            for block, flag in zip(content, note_flags, strict=True)
            if not _is_heading(block, body_size)
        ):
            note_flags = [False] * len(content)
        for block, is_note in zip(content, note_flags, strict=True):
            if is_note:
                paragraphs.extend(_parse_notes(block, page_number, notes))
            else:
                paragraphs.append(
                    _body_text(block, page_number, mark_anchors=note_size is not None)
                )
        page_texts.append([p for p in paragraphs if p])
    return page_texts, notes


def _pairing_holds(page_texts: list[list[str]], notes: list[tuple[int, Footnote]]) -> bool:
    """True if at least half the notes found their anchor in the body text."""
    text = "\n".join(p for page in page_texts for p in page)
    markers = set(re.findall(r"\[\^([^\]]+)\]", text))
    anchored = sum(note.ref in markers for _, note in notes)
    return anchored >= len(notes) / 2


_BODY_START = re.compile(r"^\s*(\d+[.\s]|introduction\b|prologue\b|part\b|chapter\b)", re.I)


def _split_sections(
    page_texts: list[list[str]],
    notes: list[tuple[int, Footnote]],
    outline: list[list],
) -> list[Section]:
    """Divide the pages into sections along the PDF outline's top level.

    Outline entries before the first body-looking one (a numbered chapter,
    "Introduction", "Part …") are lumped into a single front matter
    section. Without an outline the whole book is one section.
    """
    entries = []
    for level, title, page in outline:
        if level != 1 or not 1 <= page <= len(page_texts):
            continue
        # Only starts that advance make a section: stray bookmarks pointing
        # backwards ("Blank Page" links are common) would otherwise create
        # overlapping ranges that duplicate whole swathes of the book.
        if entries and page <= entries[-1][1]:
            continue
        entries.append((" ".join(title.split()), page))
    first_body = next((i for i, (title, _) in enumerate(entries) if _BODY_START.match(title)), 0)
    bounds = [("Front matter", 1)] if first_body > 0 else []
    bounds += entries[first_body:]
    if not bounds:
        bounds = [("Text", 1)]

    sections = []
    for (title, start), (_, next_start) in itertools.pairwise([*bounds, ("", len(page_texts) + 1)]):
        end = max(next_start - 1, start)
        text = "\n\n".join(p for page in page_texts[start - 1 : end] for p in page)
        section_notes = [note for page, note in notes if start <= page <= end]
        if text or section_notes:
            sections.append(Section(title=title, text=text, footnotes=section_notes))
    return sections


def _page_blocks(page: pymupdf.Page) -> list[list[list[_Span]]]:
    """The page's text blocks as lines of spans, skipping empty ones."""
    blocks = []
    for block in page.get_text("dict")["blocks"]:
        if block["type"] != 0:
            continue
        lines = [
            [
                _Span(
                    text=span["text"],
                    size=span["size"],
                    superscript=bool(span["flags"] & _SUPERSCRIPT_FLAG),
                )
                for span in line["spans"]
            ]
            for line in block["lines"]
        ]
        lines = [line for line in lines if any(span.text.strip() for span in line)]
        if lines:
            blocks.append(lines)
    return blocks


def _font_profile(pages: list[list[list[list[_Span]]]]) -> tuple[float, float | None]:
    """The dominant body font size, and the footnote size if the book has one.

    Sizes are weighted by how many characters they set. The footnote size
    is the heaviest size clearly smaller than the body; if none carries
    real weight (scanned books, unannotated PDFs), there are no footnotes
    to find.
    """
    weights: Counter[float] = Counter()
    for blocks in pages:
        for block in blocks:
            for line in block:
                for span in line:
                    if not span.superscript:
                        weights[round(span.size, 1)] += len(span.text)
    if not weights:
        return 0.0, None
    body_size = weights.most_common(1)[0][0]
    smaller = {s: w for s, w in weights.items() if s < body_size - 0.5}
    if not smaller:
        return body_size, None
    note_size = max(smaller, key=smaller.get)  # type: ignore[arg-type]
    if smaller[note_size] < weights[body_size] * 0.05:
        return body_size, None
    return body_size, note_size


def _dominant_size(block: list[list[_Span]]) -> float:
    weights: Counter[float] = Counter()
    for line in block:
        for span in line:
            if not span.superscript:
                weights[round(span.size, 1)] += len(span.text)
    return weights.most_common(1)[0][0] if weights else 0.0


def _is_heading(block: list[list[_Span]], body_size: float) -> bool:
    return _dominant_size(block) > body_size + _HEADING_MARGIN


def _merge_wrapped_headings(
    blocks: list[list[list[_Span]]], body_size: float
) -> list[list[list[_Span]]]:
    """Rejoin headings the typesetting wraps into one block per line.

    Consecutive blocks set in the same above-body face are one heading; a
    different face, or any body text in between, starts afresh.
    """
    merged: list[list[list[_Span]]] = []
    for block in blocks:
        if (
            merged
            and _is_heading(block, body_size)
            and _dominant_size(block) == _dominant_size(merged[-1])
        ):
            merged[-1] = merged[-1] + block
        else:
            merged.append(block)
    return merged


def _is_note_block(block: list[list[_Span]], body_size: float, note_size: float | None) -> bool:
    if note_size is None:
        return False
    dominant = _dominant_size(block)
    return abs(dominant - note_size) < abs(dominant - body_size)


def _parse_notes(
    block: list[list[_Span]], page_number: int, notes: list[tuple[int, Footnote]]
) -> list[str]:
    """Add the block's notes to ``notes`` as (page, footnote) pairs, line by line.

    A line opening with "N." starts note N of this page; other lines
    continue the previous note, provided that note started on this page or
    the one before (notes do run over page breaks). Lines that belong to no
    note — small-face content like index entries whose running head dodged
    the furniture filter — are returned so the caller can keep them as
    body text instead.
    """
    leftovers = []
    for line in block:
        text = _flatten("".join(span.text for span in line))
        if not text:
            continue
        if start := _NOTE_START.match(text):
            number, body = start.groups()
            notes.append((page_number, Footnote(ref=f"p{page_number}-n{number}", text=body)))
        elif notes and page_number - notes[-1][0] <= 1:
            last = notes[-1][1]
            last.text = _flatten(f"{last.text} {text}")
        else:
            leftovers.append(text)
    return leftovers


def _body_text(block: list[list[_Span]], page_number: int, mark_anchors: bool) -> str:
    """Flatten a body block, replacing superscript note anchors with markers."""
    lines = []
    for line in block:
        parts = []
        for span in line:
            anchor = span.text.strip()
            if mark_anchors and span.superscript and anchor.isdigit():
                parts.append(f"[^p{page_number}-n{anchor}]")
            else:
                parts.append(span.text)
        lines.append("".join(parts))
    return _flatten("\n".join(lines))


def _plain_text(block: list[list[_Span]]) -> str:
    return _flatten("\n".join("".join(span.text for span in line) for line in block))


def _normalize(paragraph: str) -> str:
    """Collapse a paragraph for repetition matching: case, spacing, page numbers.

    Running heads vary only by page number ("Greek Medicine Men 137") and
    OCR often letter-spaces them ("THE T R E E OF G N O S I S"), so digits
    and whitespace are removed entirely.
    """
    return re.sub(r"[\s\d]+", "", paragraph).lower()


def _furniture(pages: list[list[list[list[_Span]]]]) -> set[str]:
    """Normalized forms of short blocks recurring on enough pages to be furniture.

    Blocks are counted twice over: everywhere on the page against a
    threshold scaled to the book, and at the page's edges (first and last
    block — where running heads and feet live) against a low fixed one,
    so the running heads of short chapters don't slip through.
    """
    counts: Counter[str] = Counter()
    edges: Counter[str] = Counter()
    for blocks in pages:
        texts = [text for text in (_plain_text(b) for b in blocks) if text]
        short = {text for text in texts if len(text) <= _FURNITURE_MAX_CHARS}
        counts.update(_normalize(text) for text in short)
        if texts:
            edges.update(_normalize(text) for text in {texts[0], texts[-1]} & short)
    threshold = max(3, len(pages) // 20)
    furniture = {key for key, count in counts.items() if count >= threshold and key}
    furniture |= {key for key, count in edges.items() if count >= _EDGE_THRESHOLD and key}
    return furniture


def _is_page_furniture(paragraph: str, furniture: set[str]) -> bool:
    if _PAGE_NUMBER.match(paragraph):
        return True
    return len(paragraph) <= _FURNITURE_MAX_CHARS and _normalize(paragraph) in furniture


def _flatten(block: str) -> str:
    """Turn a block into one line, repairing hyphenation across line breaks."""
    text = _CONTROL.sub("", _SOFT_HYPHEN.sub("", block.strip()))
    return " ".join(_HYPHEN_BREAK.sub("", text).split())
