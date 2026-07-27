"""EPUB extraction.

An EPUB is a zip archive of XHTML chapters: ``META-INF/container.xml``
points at an OPF manifest whose spine lists the chapters in reading order.
Footnotes are marked up with ``epub:type`` (footnote/endnote/rearnote) or
DPUB-ARIA ``role`` attributes, anchored in the running text by ``noteref``
links. Books without any semantic markup fall back to the endnotes-chapter
heuristics in :mod:`extraction.endnotes`, and failing that, to a lower-level
reciprocal-link reading (:func:`_pull_href_footnotes`) for notes cross-linked
by nothing but a plain ``<a id=.. href=..>`` pair on each side.
"""

import zipfile
from collections import Counter
from pathlib import Path, PurePosixPath
from urllib.parse import unquote
from xml.etree import ElementTree

from bs4 import BeautifulSoup, Tag

from extraction.base import (
    BIBLIOGRAPHY_TITLE,
    BibliographyEntry,
    Extraction,
    Footnote,
    Metadata,
    Section,
)
from extraction.endnotes import pull_endnotes

_CONTAINER = "META-INF/container.xml"
_CONTAINER_NS = {"c": "urn:oasis:names:tc:opendocument:xmlns:container"}
_OPF_NS = {"opf": "http://www.idpf.org/2007/opf"}
_OPF_URI = _OPF_NS["opf"]
_DC_NS = {"dc": "http://purl.org/dc/elements/1.1/"}

_NOTE_TYPES = frozenset({"footnote", "endnote", "rearnote", "doc-footnote", "doc-endnote"})
_NOTEREF_TYPES = frozenset({"noteref", "doc-noteref"})
_BLOCK_TAGS = ["h1", "h2", "h3", "h4", "h5", "h6", "p", "li", "blockquote", "div"]
_HEADING_TAGS = frozenset({"h1", "h2", "h3", "h4", "h5", "h6"})
_MAX_TITLE_LENGTH = 60


class EpubExtractor:
    def extract(self, document: Path) -> Extraction:
        with zipfile.ZipFile(document) as archive:
            paths = _chapter_paths(archive)
            soups = [BeautifulSoup(archive.read(path), "html.parser") for path in paths]
            leaves = _nav_leaves(archive)
        footnotes: list[Footnote] = []
        for soup in soups:
            footnotes.extend(_pull_footnotes(soup))
            _mark_noterefs(soup)
        if not footnotes:
            footnotes = pull_endnotes(soups)
        if not footnotes:
            footnotes = _pull_href_footnotes(paths, soups)
        if not leaves:
            bibliography = []
            for soup in soups:
                entries, _ = _pull_bibliography(soup)
                bibliography.extend(entries)
            text = "\n\n".join(part for soup in soups if (part := _running_text(soup)))
            section = Section(
                title="Full text", text=text, footnotes=footnotes, bibliography=bibliography
            )
            return Extraction(sections=[section])
        return Extraction(sections=_split_sections(paths, soups, leaves, footnotes))


def _chapter_paths(archive: zipfile.ZipFile) -> list[str]:
    """Return the archive paths of the spine's XHTML chapters, in reading order.

    ``linear="no"`` itemrefs (a duplicate cover page, the interactive nav
    document itself) are auxiliary, not part of the book's own reading
    order — Couliano's *Eros and Magic* marks both this way, and the nav
    document's own ``<li>`` list would otherwise read as running-text
    paragraphs, one chapter title per "line".
    """
    container = ElementTree.fromstring(archive.read(_CONTAINER))
    opf_path = container.find(".//c:rootfile", _CONTAINER_NS).attrib["full-path"]
    opf = ElementTree.fromstring(archive.read(opf_path))
    opf_dir = PurePosixPath(opf_path).parent

    items = {item.attrib["id"]: item for item in opf.findall(".//opf:manifest/opf:item", _OPF_NS)}
    return [
        str(opf_dir / unquote(item.attrib["href"]))
        for ref in opf.findall(".//opf:spine/opf:itemref", _OPF_NS)
        if ref.attrib.get("linear", "yes") != "no"
        and (item := items[ref.attrib["idref"]]).attrib.get("media-type") == "application/xhtml+xml"
    ]


def read_metadata(document: Path) -> Metadata:
    """The OPF's own ``<metadata>`` block: title, author, language, year, publisher.

    A creator's ``opf:role`` decides whether it's an author: authors get no
    role at all as often as they get "aut" explicitly (EPUB2 conventions
    vary), so a missing role defaults to "aut" rather than excluding the
    creator; a translator or other contributor is marked with a different
    role and correctly left out. ``dc:date`` is the book's own publication
    date, not Calibre's conversion timestamp (that lives in a separate
    ``<meta name="calibre:timestamp">``), so its year is trustworthy as-is.
    """
    with zipfile.ZipFile(document) as archive:
        container = ElementTree.fromstring(archive.read(_CONTAINER))
        opf_path = container.find(".//c:rootfile", _CONTAINER_NS).attrib["full-path"]
        opf = ElementTree.fromstring(archive.read(opf_path))
    meta = opf.find(".//opf:metadata", _OPF_NS)
    if meta is None:
        return Metadata()
    title = _dc_text(meta, "title")
    authors = [
        creator.text.strip()
        for creator in meta.findall("dc:creator", _DC_NS)
        if creator.text and creator.get(f"{{{_OPF_URI}}}role", "aut") == "aut"
    ]
    date = _dc_text(meta, "date")
    return Metadata(
        title=title,
        author="; ".join(authors) or None,
        language=_dc_text(meta, "language"),
        year=date[:4] if date and date[:4].isdigit() else None,
        publisher=_dc_text(meta, "publisher"),
    )


def _dc_text(meta: ElementTree.Element, tag: str) -> str | None:
    element = meta.find(f"dc:{tag}", _DC_NS)
    return element.text.strip() if element is not None and element.text else None


_NCX_NS = {"n": "http://www.daisy.org/z3986/2005/ncx/"}


def _nav_leaves(archive: zipfile.ZipFile) -> list[tuple[str, str, str | None]]:
    """The book's chapter/part tree, flattened to its leaves: (title, path, fragment).

    A navPoint with children is a Part, not a chapter — only leaves become
    sections, so a Part heading doesn't swallow every chapter beneath it into
    one section spanning several (this corpus's EPUBs nest chapters three
    navPoints deep: Part > Chapter). Read from the NCX the spine's ``toc``
    attribute names; both EPUBs validated against so far are Calibre/EPUB2
    productions with no EPUB3 nav document to prefer instead, so that path
    isn't built until a real one shows up.
    """
    container = ElementTree.fromstring(archive.read(_CONTAINER))
    opf_path = container.find(".//c:rootfile", _CONTAINER_NS).attrib["full-path"]
    opf = ElementTree.fromstring(archive.read(opf_path))
    opf_dir = PurePosixPath(opf_path).parent

    items = {item.attrib["id"]: item for item in opf.findall(".//opf:manifest/opf:item", _OPF_NS)}
    spine = opf.find(".//opf:spine", _OPF_NS)
    ncx_item = items.get(spine.attrib.get("toc")) if spine is not None else None
    if ncx_item is None:
        return []

    ncx_path = str(opf_dir / unquote(ncx_item.attrib["href"]))
    ncx_dir = PurePosixPath(ncx_path).parent
    ncx = ElementTree.fromstring(archive.read(ncx_path))
    top = ncx.findall("./n:navMap/n:navPoint", _NCX_NS)
    return _flatten_navmap(top, ncx_dir)


def _flatten_navmap(
    points: list[ElementTree.Element], base_dir: PurePosixPath
) -> list[tuple[str, str, str | None]]:
    leaves: list[tuple[str, str, str | None]] = []
    for point in points:
        children = point.findall("n:navPoint", _NCX_NS)
        if children:
            leaves.extend(_flatten_navmap(children, base_dir))
            continue
        label = point.find("n:navLabel/n:text", _NCX_NS)
        content = point.find("n:content", _NCX_NS)
        if label is None or label.text is None or content is None or not content.attrib.get("src"):
            continue
        path, _, fragment = unquote(content.attrib["src"]).partition("#")
        leaves.append((" ".join(label.text.split()), str(base_dir / path), fragment or None))
    return leaves


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


def _pull_bibliography(soup: BeautifulSoup) -> tuple[list[BibliographyEntry], str | None]:
    """Detach a bibliography chapter's entries and return them, verbatim.

    Unlike the PDF path, there's no hanging-indent geometry to reconstruct:
    an EPUB paragraph already bounds one entry, since the source never lost
    that structure the way a PDF's text layer does. Just find the heading
    and take the ``<p>``/``<li>`` siblings that follow it, stopping at the
    next heading (or the file's end) so a chapter that bundles the
    bibliography with something else (an index, an afterword) doesn't bleed
    into this list.

    A real chapter title is short; a body paragraph that happens to contain
    the word "references" in passing ("her speech was filled with
    references…", a real match found in this corpus) is not — some EPUB
    conversions mistag long paragraphs as heading elements, so title length
    is checked alongside the word match rather than trusting the tag alone.

    A long entry can itself land as two ``<p>`` elements (a source-line-wrap
    the conversion turned into a paragraph break, seen in 11 of this
    corpus's 112 entries) — a paragraph that doesn't end in terminal
    punctuation is a continuation of the previous one, not a new entry, the
    same call ``SeamMender`` makes for prose torn by a page break.

    Also returns the heading's own fragment id (or ``None``), read before
    it's extracted — the caller uses it to attribute these entries to the
    right leaf section when a file holds more than one.
    """
    heading = soup.find(
        lambda tag: (
            tag.name in _HEADING_TAGS
            and len(title := tag.get_text(" ", strip=True)) <= _MAX_TITLE_LENGTH
            and BIBLIOGRAPHY_TITLE.search(title)
        )
    )
    if heading is None:
        return [], None
    heading_id = heading.get("id")
    texts: list[str] = []
    for sibling in list(heading.find_next_siblings()):
        if sibling.name in _HEADING_TAGS:
            break
        if sibling.name in ("p", "li") and (text := sibling.get_text(" ", strip=True)):
            if texts and not _ends_entry(texts[-1]):
                texts[-1] = f"{texts[-1]} {text}"
            else:
                texts.append(text)
        sibling.extract()
    heading.extract()
    return [BibliographyEntry(text=text) for text in texts], heading_id


def _ends_entry(text: str) -> bool:
    return text.rstrip("\"'’”").endswith((".", "?", "!"))  # noqa: RUF001


def _mark_noterefs(soup: BeautifulSoup) -> None:
    """Replace footnote anchors with ``[^ref]`` markers tying them to their notes."""
    for anchor in soup.find_all(lambda tag: _semantic_types(tag) & _NOTEREF_TYPES):
        ref = (anchor.get("href") or "").rpartition("#")[2]
        anchor.replace_with(f"[^{ref}]")


def _resolve_href(path: str, href: str) -> tuple[str, str] | None:
    """A same- or cross-file ``href``'s target as (path, fragment); ``None`` if bare."""
    file_part, sep, fragment = href.partition("#")
    if not sep or not fragment:
        return None
    target_path = path if not file_part else str(PurePosixPath(path).parent / unquote(file_part))
    return target_path, fragment


def _links_back(target: Tag, target_path: str, path: str, own_id: str) -> bool:
    """Whether ``target`` (or a link nested inside it) points back at ``(path, own_id)``.

    ``target`` itself carries the id being linked to; the actual ``href``
    that should round-trip back to the caller can sit on ``target`` itself
    (a note number that *is* an ``<a>``) or on a descendant ``<a>`` (a note
    body ``<div>`` whose own number is one of its children) — either way,
    still this note's own back-reference.
    """
    candidates = target.find_all("a", href=True)
    if target.name == "a" and target.get("href"):
        candidates = [target, *candidates]
    return any(_resolve_href(target_path, a["href"]) == (path, own_id) for a in candidates)


def _pull_href_footnotes(paths: list[str], soups: list[BeautifulSoup]) -> list[Footnote]:
    """Fallback for notes cross-linked by plain ``<a id=.. href=..>`` pairs, no semantics.

    Some conversions link a noteref to its note with nothing but a pair of
    ordinary anchors, each carrying the other's id in its own ``href`` — no
    ``epub:type``/``role`` markup, so ``_pull_footnotes`` finds nothing; the
    notes chapter itself is often ``<div>``-based rather than ``<p>``-based
    too, so ``pull_endnotes``'s bare-``<sup>``-plus-heading heuristic
    (matched by section and number) misses it as well. Read reciprocity
    directly instead: an anchor with an id and an href is a genuine
    noteref/note pair only if the element its ``href`` resolves to *also*
    links back to this anchor's own id — an ordinary cross-reference (an
    index's page-number link, a "see also") never does, since only a
    footnote apparatus round-trips both ways in this markup style. Which
    side of a confirmed pair is "the note" (as opposed to "the noteref",
    left in running text) is read off which file the pair's two ends
    actually live in: a shared notes chapter is the target of every
    chapter's own pairs, so it accumulates far more pair-endpoints than any
    one body chapter does — no heading-text guess needed.
    """
    ids: dict[tuple[str, str], Tag] = {}
    for path, soup in zip(paths, soups, strict=True):
        for tag in soup.find_all(id=True):
            ids[(path, tag["id"])] = tag

    pairs: dict[frozenset, tuple[str, str, str, str]] = {}
    for path, soup in zip(paths, soups, strict=True):
        for anchor in soup.find_all("a", id=True, href=True):
            own_id = anchor["id"]
            resolved = _resolve_href(path, anchor["href"])
            if resolved is None:
                continue
            target_path, target_frag = resolved
            target = ids.get((target_path, target_frag))
            if target is None or not _links_back(target, target_path, path, own_id):
                continue
            key = frozenset({(path, own_id), (target_path, target_frag)})
            pairs[key] = (path, own_id, target_path, target_frag)

    if not pairs:
        return []

    touches = Counter(path for pair in pairs.values() for path in (pair[0], pair[2]))
    notes_path, _ = touches.most_common(1)[0]

    footnotes = []
    for path, own_id, target_path, target_frag in pairs.values():
        if target_path == notes_path and path != notes_path:
            note_id, note_path, ref_path, ref_id = target_frag, target_path, path, own_id
        elif path == notes_path and target_path != notes_path:
            note_id, note_path, ref_path, ref_id = own_id, path, target_path, target_frag
        else:
            continue  # both ends in (or both out of) the notes file: not a real pair
        note = ids[(note_path, note_id)]
        container = note if note.name in _BLOCK_TAGS else note.find_parent(_BLOCK_TAGS)
        if container is None:
            continue
        for backlink in container.find_all("a", href=True):
            if _resolve_href(note_path, backlink["href"]) == (ref_path, ref_id):
                backlink.extract()
        footnotes.append(Footnote(ref=note_id, text=container.get_text(" ", strip=True)))
        container.extract()
        anchor = ids[(ref_path, ref_id)]
        anchor.replace_with(f"[^{note_id}]")
    return footnotes


def _running_text(soup: BeautifulSoup) -> str:
    """Flatten a chapter to plain text, one blank line between blocks."""
    return _blocks_text(_top_level_blocks(soup))


def _top_level_blocks(container: Tag) -> list[tuple[Tag, str]]:
    """The document's own paragraph-level units: (owning tag, text) pairs, in order.

    Some conversions wrap every paragraph in its own ``<div class="...">``
    rather than a ``<p>``, with an outer wrapper ``<div>`` around the whole
    chapter body (seen in several Routledge/Taylor & Francis EPUBs — Yates'
    *Lull and Bruno*, *Ideas and Ideals*, Coetzee's *Stranger Shores*). A
    block tag can also — in malformed but real markup, e.g. an epigraph
    couplet in Couliano's *Eros and Magic* — own text of its own *and* nest
    a further block tag inside it (a heading directly wrapping a citation
    line, ended by a stray ``<p>``). Splitting only at block-tag boundaries
    (rather than picking either the outermost or the innermost block
    wholesale) handles both: a div-wrapped paragraph and a bare ``<p>``
    each become their own single unit; a block tag with mixed content
    contributes its own directly-owned text as one unit and each nested
    block tag as further units, in document order, rather than either
    merging everything into one blob (losing paragraph structure) or
    silently dropping the outer tag's own text (losing content).
    """
    units: list[tuple[Tag, str]] = []
    buffer: list[str] = []

    def flush(owner: Tag) -> None:
        text = " ".join("".join(buffer).split())
        # Text owned by ``container`` itself — never a real paragraph tag,
        # only the placeholder scope for content encountered before the
        # first block tag anywhere in the document (an XML declaration, a
        # leaked <title>) — isn't a paragraph unit; it also can't safely be
        # attributed a real owner, since it sits outside every block tag.
        if text and owner is not container:
            units.append((owner, text))
        buffer.clear()

    def walk(node: Tag, owner: Tag) -> None:
        # A non-block tag (span, html, body, an unrecognised wrapper...) is
        # descended into transparently, under the *same* owner/buffer, so a
        # block tag nested arbitrarily deep inside one is still found rather
        # than the whole wrapper being flattened by one get_text() call —
        # the bug an earlier version of this function had, which merged an
        # entire chapter's headings and paragraphs into a single unit
        # whenever they sat under so much as a bare ``<body>``.
        for child in node.children:
            if isinstance(child, Tag):
                if child.name in _BLOCK_TAGS:
                    flush(owner)
                    walk(child, child)
                    flush(child)
                else:
                    walk(child, owner)
            else:
                buffer.append(str(child))

    walk(container, container)
    flush(container)
    return units


def _blocks_text(blocks: list[tuple[Tag, str]]) -> str:
    return "\n\n".join(text for _, text in blocks)


def _find_leaf_block(
    blocks: list[tuple[Tag, str]], fragment: str, soup: BeautifulSoup
) -> int | None:
    """The index of the top-level block a leaf's fragment id resolves to.

    Resolves the id to its nearest enclosing block tag, then picks the
    first unit whose owner is that tag or comes after it in document order
    — rather than a pure containment check, which breaks when the id's own
    block produced no unit at all: a bookmark anchor plus a full-page
    illustration and nothing else (real markup, in one Yates EPUB's
    chapter-opener pages) is an empty paragraph, so no owner is ever equal
    to or a descendant of it, even though the fragment is completely valid
    and the next block over — the actual chapter title — is exactly the
    right split point. Document order is read off ``soup.find_all`` over
    every block tag, wrapper and leaf alike, since a walk that assigns each
    block-tag element to a unit only when it's non-empty preserves that
    same relative order among the ones that do.
    """
    target = soup.find(id=fragment)
    if target is None:
        return None
    holder = target if target.name in _BLOCK_TAGS else target.find_parent(_BLOCK_TAGS)
    if holder is None:
        return None
    order = {id(tag): i for i, tag in enumerate(soup.find_all(_BLOCK_TAGS))}
    holder_order = order[id(holder)]
    for i, (owner, _) in enumerate(blocks):
        if order[id(owner)] >= holder_order:
            return i
    return None


def _split_sections(
    paths: list[str],
    soups: list[BeautifulSoup],
    leaves: list[tuple[str, str, str | None]],
    footnotes: list[Footnote],
) -> list[Section]:
    """Divide a book's chapter files into sections along its own navigation tree.

    A file with no leaf pointing to it is front matter (before the first
    leaf), back matter (after the last), or — the common case, since
    Calibre splits a long chapter across several physical files but the nav
    only ever points at the first — a continuation folded into whichever
    leaf precedes it, rather than an unnamed section of its own. Bibliography
    entries pulled from a file attach to the leaf whose fragment matches the
    heading's own id, or to that file's own (usually sole) leaf when the
    heading has none. Footnotes attach to whichever section's own text
    actually carries their ``[^ref]`` marker, since one notes-chapter's
    entries (the endnotes fallback) land across several leaf sections, keyed
    by which chapter's body the marker itself ended up in — not by which
    leaf the note text was pulled from.
    """
    by_path: dict[str, list[tuple[int, str | None]]] = {}
    for index, (_, path, fragment) in enumerate(leaves):
        by_path.setdefault(path, []).append((index, fragment))

    texts: list[list[str]] = [[] for _ in leaves]
    bibliographies: list[list[BibliographyEntry]] = [[] for _ in leaves]
    front_matter: list[str] = []
    back_matter: list[str] = []
    current = -1

    for path, soup in zip(paths, soups, strict=True):
        entries, heading_id = _pull_bibliography(soup)
        blocks = _top_level_blocks(soup)
        own_leaves = by_path.get(path)

        if own_leaves is None:
            # A chapter split across several files (Calibre's own doing) only
            # has its first file as a nav leaf; the rest carry no leaf of
            # their own and continue whichever chapter is still open, not
            # "back matter" — that label is reserved for content past the
            # book's very last leaf.
            text = _blocks_text(blocks)
            if current == -1:
                bucket = front_matter
            elif current == len(leaves) - 1:
                bucket = back_matter
            else:
                bucket = texts[current]
            if text:
                bucket.append(text)
            if entries:
                bucket.extend(entry.text for entry in entries)
            continue

        bounds = sorted(
            (0 if fragment is None else (_find_leaf_block(blocks, fragment, soup) or 0), index)
            for index, fragment in own_leaves
        )
        if bounds[0][0] > 0:
            lead = _blocks_text(blocks[: bounds[0][0]])
            if lead:
                (texts[current] if current >= 0 else front_matter).append(lead)
        for i, (start, index) in enumerate(bounds):
            end = bounds[i + 1][0] if i + 1 < len(bounds) else len(blocks)
            text = _blocks_text(blocks[start:end])
            if text:
                texts[index].append(text)
            current = index
        if entries:
            target = next((i for i, f in own_leaves if f == heading_id), own_leaves[0][0])
            bibliographies[target].extend(entries)

    sections = []
    if front_matter:
        sections.append(Section(title="Front matter", text="\n\n".join(front_matter)))
    for (title, _, _), text, bibliography in zip(leaves, texts, bibliographies, strict=True):
        body = "\n\n".join(text)
        section_notes = [note for note in footnotes if f"[^{note.ref}]" in body]
        if body or bibliography or section_notes:
            sections.append(
                Section(title=title, text=body, footnotes=section_notes, bibliography=bibliography)
            )
    if back_matter:
        sections.append(Section(title="Back matter", text="\n\n".join(back_matter)))
    return sections
