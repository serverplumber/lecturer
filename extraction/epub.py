"""EPUB extraction.

An EPUB is a zip archive of XHTML chapters: ``META-INF/container.xml``
points at an OPF manifest whose spine lists the chapters in reading order.
Footnotes are marked up with ``epub:type`` (footnote/endnote/rearnote) or
DPUB-ARIA ``role`` attributes, anchored in the running text by ``noteref``
links. Books without any semantic markup fall back to the endnotes-chapter
heuristics in :mod:`extraction.endnotes`.
"""

import zipfile
from pathlib import Path, PurePosixPath
from urllib.parse import unquote
from xml.etree import ElementTree

from bs4 import BeautifulSoup, Tag

from extraction.base import Extraction, Footnote, Section
from extraction.endnotes import pull_endnotes

_CONTAINER = "META-INF/container.xml"
_CONTAINER_NS = {"c": "urn:oasis:names:tc:opendocument:xmlns:container"}
_OPF_NS = {"opf": "http://www.idpf.org/2007/opf"}

_NOTE_TYPES = frozenset({"footnote", "endnote", "rearnote", "doc-footnote", "doc-endnote"})
_NOTEREF_TYPES = frozenset({"noteref", "doc-noteref"})
_BLOCK_TAGS = ["h1", "h2", "h3", "h4", "h5", "h6", "p", "li", "blockquote"]


class EpubExtractor:
    def extract(self, document: Path) -> Extraction:
        with zipfile.ZipFile(document) as archive:
            soups = [
                BeautifulSoup(archive.read(chapter), "html.parser")
                for chapter in _chapter_paths(archive)
            ]
        footnotes: list[Footnote] = []
        for soup in soups:
            footnotes.extend(_pull_footnotes(soup))
            _mark_noterefs(soup)
        if not footnotes:
            footnotes = pull_endnotes(soups)
        text = "\n\n".join(part for soup in soups if (part := _running_text(soup)))
        # TODO: split into per-chapter sections along the spine/nav once the
        # epub path gets the same treatment as PDFs.
        return Extraction(sections=[Section(title="Full text", text=text, footnotes=footnotes)])


def _chapter_paths(archive: zipfile.ZipFile) -> list[str]:
    """Return the archive paths of the spine's XHTML chapters, in reading order."""
    container = ElementTree.fromstring(archive.read(_CONTAINER))
    opf_path = container.find(".//c:rootfile", _CONTAINER_NS).attrib["full-path"]
    opf = ElementTree.fromstring(archive.read(opf_path))
    opf_dir = PurePosixPath(opf_path).parent

    items = {item.attrib["id"]: item for item in opf.findall(".//opf:manifest/opf:item", _OPF_NS)}
    return [
        str(opf_dir / unquote(item.attrib["href"]))
        for ref in opf.findall(".//opf:spine/opf:itemref", _OPF_NS)
        if (item := items[ref.attrib["idref"]]).attrib.get("media-type") == "application/xhtml+xml"
    ]


def _semantic_types(tag: Tag) -> set[str]:
    """The EPUB/ARIA semantics of a tag; both attributes hold space-separated tokens."""
    return set((tag.get("epub:type") or "").split()) | set((tag.get("role") or "").split())


def _pull_footnotes(soup: BeautifulSoup) -> list[Footnote]:
    """Detach footnote elements from the document and return them."""
    notes = []
    for element in soup.find_all(lambda tag: _semantic_types(tag) & _NOTE_TYPES):
        element.extract()
        notes.append(Footnote(ref=element.get("id", ""), text=element.get_text(" ", strip=True)))
    return notes


def _mark_noterefs(soup: BeautifulSoup) -> None:
    """Replace footnote anchors with ``[^ref]`` markers tying them to their notes."""
    for anchor in soup.find_all(lambda tag: _semantic_types(tag) & _NOTEREF_TYPES):
        ref = (anchor.get("href") or "").rpartition("#")[2]
        anchor.replace_with(f"[^{ref}]")


def _running_text(soup: BeautifulSoup) -> str:
    """Flatten a chapter to plain text, one blank line between blocks."""
    blocks = [b for b in soup.find_all(_BLOCK_TAGS) if b.find_parent(_BLOCK_TAGS) is None]
    if not blocks:
        return soup.get_text(" ", strip=True)
    return "\n\n".join(text for b in blocks if (text := b.get_text(" ", strip=True)))
