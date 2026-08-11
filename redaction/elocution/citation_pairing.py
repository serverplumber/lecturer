"""Author-siglum pairing — reading a document's own sigla off its footnotes.

``docs/elocution.md``'s ``truncation_aligner`` (component 6) was meant to
discover a document's classical/patristic sigla by aligning a bibliography
entry's own title text against the abbreviation a footnote uses for it. That
doesn't work for this corpus: primary sources are collected Loeb-style
bibliography entries with no per-work title to align against ("Cassius Dio.
Roman History." tells you nothing about "57.25.8" naming a book-and-chapter
of it), and the citations themselves never abbreviate an author's own name,
only the work.

But a citation doesn't need title-alignment to teach you its siglum, because
the footnotes already say the author's name out loud at the citation itself
- "Josephus, AJ 18.81-84", "Tacitus, Ann. 2.32", "Suetonius, Ner. 49.2". This
is the literal code behind ``classical.py``'s "never resolve author/work
identity - the surrounding prose already supplies it": the prose *does* name
the author, right there, so this reads that fact structurally instead of
asking anything (LLM or heuristic) to guess it. No identity resolution
happens here at all — the author is only ever accepted from
``bibliography.py``'s own ``is_primary_source`` list, never inferred.

Some authors are cited with no siglum at all ("Livy, 1.36.2-6", "Cassius
Dio, 57.25.8") - one work, nothing to abbreviate - which is itself useful:
it says this author's table entry should map straight to a bare locator,
not to some invented siglum.

This only pairs an author with a siglum where the footnotes name both
together. A siglum reused bare on a later citation in the same footnote
("Peregr. 28" after "Lucian, Alex. 11" established Lucian two sentences
earlier) is real signal this pass doesn't capture — measure how much of the
corpus that leaves on the table before building a register for it; don't
build the register speculatively.
"""

import re
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass

from extraction.base import Footnote
from redaction.elocution.base import LOCATOR
from redaction.elocution.bibliography import BibliographyEntry

_SIGLUM_TOKEN = r"[A-Za-z][\w.'&-]*"
_SIGLUM = rf"{_SIGLUM_TOKEN}(?:\s+{_SIGLUM_TOKEN}){{0,4}}"


_MAX_CITATIONS = 3
# A sample, not the full count -- a siglum cited a dozen times doesn't need a
# dozen locators to check by hand, and every footnote here numbers by page
# (``[^p59-n69]``, this corpus's own convention), so ``ref`` alone is already
# a direct grep target against ``sections/*.footnotes.txt`` regardless of
# which page or chapter it actually falls on.


@dataclass(frozen=True)
class Citation:
    """Where one citation actually sits — enough to find it again by hand.

    ``ref`` is the footnote's own id (``Footnote.ref``); ``[^{ref}]`` is the
    literal anchor ``write_sections`` writes into ``sections/*.footnotes.txt``,
    so it's directly greppable. ``locator`` is the citation's own numeric
    locator ("15.44") — extra confirmation once you're looking at the note,
    since one footnote can carry more than one citation.
    """

    ref: str
    locator: str


@dataclass(frozen=True)
class SiglumPairing:
    """One (author, siglum) pair the footnotes actually paired, and how often.

    ``siglum`` is ``None`` when the author is cited by a bare locator with
    no work abbreviation at all — a real, useful outcome, not a miss.
    ``citations`` is a capped sample (``_MAX_CITATIONS``) of where this
    pairing actually occurs, for a human to check against the source rather
    than trust ``count`` alone.
    """

    author: str
    siglum: str | None
    count: int
    citations: tuple[Citation, ...] = ()


def known_primary_authors(entries: Sequence[BibliographyEntry]) -> list[str]:
    """This document's confirmed primary-source authors, longest name first.

    Only entries ``bibliography.py`` already scored ``is_primary_source``
    contribute a name — never anything sniffed from the footnotes
    themselves, since that would be exactly the identity-guessing this
    module is built to avoid. Translator-fronted entries (empty
    ``authors``) contribute nothing: the ancient author, if named at all,
    is embedded in the title, not recoverable as a bare name to search for.
    """
    names = {name for entry in entries if entry.is_primary_source for name in entry.authors}
    return sorted(names, key=len, reverse=True)


def _citation_pattern(authors: Sequence[str]) -> re.Pattern[str]:
    author_alt = "|".join(re.escape(author) for author in authors)
    return re.compile(
        rf"\b(?P<author>{author_alt}),\s+"
        rf"(?:(?P<siglum>{_SIGLUM})\s+)?"
        rf"(?P<locator>{LOCATOR})\b"
    )


def pair_sigla(
    entries: Sequence[BibliographyEntry], footnotes: Sequence[Footnote]
) -> list[SiglumPairing]:
    """Count every (author, siglum) pairing the footnotes' own text supplies.

    One combined pass over every footnote, gated on the closed list of
    already-confirmed primary-source authors — an author absent from that
    list never enters a pairing, no matter how citation-shaped the text
    around a name looks. Alongside the count, keeps a capped sample of
    where each pairing actually occurs (``Citation``) — a locator a human
    can go check by hand rather than a bare number to take on faith.
    """
    authors = known_primary_authors(entries)
    if not authors:
        return []
    pattern = _citation_pattern(authors)
    counts: Counter[tuple[str, str | None]] = Counter()
    citations: dict[tuple[str, str | None], list[Citation]] = {}
    for note in footnotes:
        for match in pattern.finditer(note.text):
            key = (match.group("author"), match.group("siglum"))
            counts[key] += 1
            sample = citations.setdefault(key, [])
            if len(sample) < _MAX_CITATIONS:
                sample.append(Citation(ref=note.ref, locator=match.group("locator")))
    return [
        SiglumPairing(
            author=author, siglum=siglum, count=count, citations=tuple(citations[(author, siglum)])
        )
        for (author, siglum), count in counts.items()
    ]


def collisions(pairings: Sequence[SiglumPairing]) -> dict[str, set[str]]:
    """Sigla this document pairs with more than one author — never silently flattened.

    ``base.py``'s combined regex pass can hold two systems sharing a
    written siglum with different locator shapes; this only flags the
    same *shape* siglum going to different authors, which the eventual
    static table needs a human to resolve rather than pick one.
    """
    by_siglum: dict[str, set[str]] = {}
    for pairing in pairings:
        if pairing.siglum is not None:
            by_siglum.setdefault(pairing.siglum, set()).add(pairing.author)
    return {siglum: authors for siglum, authors in by_siglum.items() if len(authors) > 1}
