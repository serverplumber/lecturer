"""Bibliography entry parsing — turning a reference list into who-said-what.

See ``docs/elocution.md``'s Pass 0 (``style_sniffer``) and Pass 1 ("apparatus",
``bibliography_entry_parser``, ``primary_secondary_classifier``). Extraction
(``extraction/pdf.py``) only
recovers entry *boundaries* from page geometry — pymupdf's block detector
glues a hanging-indent list into one blob, and there's no way back to the
right split points except the layout that's already gone once the text
reaches here. What an entry *means* — who wrote it, what it's called, which
of its facts a citation-dictation system needs to resolve a siglum — is a
text-parsing problem with no geometry left to lean on, so it belongs here,
not in extraction: one dataclass, one parser, kept in a single module rather
than split across the many small files ``docs/elocution.md`` enumerates for
this pass — there's no database or service boundary here to justify carving
up what is, in practice, one parsing job over one list of strings.

The parser below knows one house style: Chicago/SBL notes-bibliography — an
inverted first author ("Surname, First M."), later authors in natural order
("First M. Last"), a same-author continuation marker in place of repeating a
name, and a title that's either quoted (an article or chapter, followed by
a journal siglum or a "Pages X-Y in <container>" clause) or plain (a book,
with the year at the entry's tail rather than its head). ``sniff_style``
confirms that shape holds for a given bibliography before the parser ever
runs against it, rather than assuming every bibliography is one — with a
corpus of one book, a parser for a style nothing here exercises would be
untestable, so an unconfirmed style abstains to raw text instead of
guessing at a shape this module has never been checked against. The one
thing that isn't assumed even when the style *is* confirmed is the
continuation marker's own dash count: sniffed from the document's own
entries rather than hardcoded to three, since that's a typesetting choice,
not part of the style itself.

Every field below is best-effort. ``text`` is always the verbatim entry,
and a failed field never suppresses it: what doesn't parse cleanly stays
available in full for the redaction layers or hand inspection rather than
disappearing.
"""

import re
from collections import Counter
from dataclasses import dataclass, field

from extraction.base import BibliographyEntry as RawEntry

_LETTER = r"[A-ZÀ-ÖØ-Þ]"
_INITIAL = rf"{_LETTER}\."
_SPELLED = rf"{_LETTER}[\w''’\-]*"  # noqa: RUF001
_GIVEN_TOKEN_RE = re.compile(rf"{_INITIAL}|{_SPELLED}")
_INITIAL_RE = re.compile(_INITIAL)
_SPELLED_RE = re.compile(_SPELLED)

_ZWS = "​"
# A same-author continuation marker is a run of one repeated dash-like
# character followed by the punctuation that would otherwise follow a name
# (a period before a title, a comma before a role marker, a colon before
# whatever this document's own grammar puts there). Neither the character
# nor the run length nor the trailing punctuation is assumed: three real
# corpora have shown three different characters (temple_gates' typeset em
# dash "———.", Couliano's *Tree of Gnosis* double hyphen "--,"/"--:", and
# his *Eros and Magic* single hyphen "-."/"-,") — sniffed per document
# rather than hardcoded, the same discipline the run *length* already had.
_DASH_CHARS = "—–-"  # noqa: RUF001
_LEADING_DASH_RUN = re.compile(rf"^(?P<char>[{_DASH_CHARS}])(?P=char)*[.,:]")
_ROLE = re.compile(r"^,?\s*(eds?|trans)\.,?\s*")
_QUOTE_OPEN = "“"
_QUOTE_CLOSE = "”"

# Year and pages/container are looked for independently rather than as one
# monolithic per-shape pattern: this corpus's tails vary too much in the
# details (roman-numeral page ranges, a stray space where a hyphenation
# artifact left one, "Publisher. Year." instead of "Publisher, Year.",
# dissertations with no journal or "Pages...in" shape at all) for a single
# regex per shape to hold up, but a *year* is reliably the last bare 4-digit
# number before the entry's own final period regardless of which of those
# shapes it is, so that one fact is split out and tried first, unconditionally.
_YEAR_IN_PARENS = re.compile(r"\((?P<year>\d{4})\)")
# A multi-volume translation published over a span ("1932-51.") ends in a
# range, not a bare year — the range's own end is elided to two digits, so
# only the first year is captured, same as a single-year entry would be.
_LAST_YEAR = re.compile(r"(?P<year>\d{4})(?:[–—-]\d{2,4})?\.?\s*$")  # noqa: RUF001
_PAGES_AFTER_COLON = re.compile(r":\s*(?P<pages>[ivxlc\d][ivxlc\d,.\-–—\s]*)")  # noqa: RUF001
# A chapter's "Pages X-Y in <container>." intro — container itself isn't
# captured here: a container title routinely has its own internal
# abbreviation period ("...Vol. 4: The Late Roman-Rabbinic Period."), so a
# non-greedy ``.+?\.`` would stop at "Vol" the same way it once did for book
# titles and editor names. Instead the container is whatever's left before
# the entry's "Edited by" credit, or (lacking one) its publication tail —
# see the two call sites below.
_CHAPTER_IN = re.compile(
    r"^Pages?\s+(?P<pages>[ivxlc\d][ivxlc\d,.\-–—\s]*?)\s+in\s+",  # noqa: RUF001
    re.IGNORECASE,
)
# Just the introducer, not the editor names themselves: a non-greedy
# ".+?\." would stop at the first initial's own period ("Paul G." instead
# of "Paul G. P. Meyboom") the same way an inverted author's given names
# would, so the names after it are consumed token-by-token instead, via
# ``_consume_editor_list``.
_EDITED_BY_INTRO = re.compile(r"Edited(?:\s+and\s+translated)?\s+by\s+", re.IGNORECASE)
# A book title's trailing publication clause: an optional series designation
# (an abbreviation ending in a number, "WUNT 232."), an optional "Place:",
# then "Publisher, Year." (or, inconsistently in this corpus, "Publisher.
# Year.") — stripped from the tail so title extraction never has to guess
# which period is the title's own; it matches the clause from the end instead.
_BOOK_TAIL = re.compile(
    r"\s*(?:[A-ZÀ-Þ][\w ,&'’\-]*\d+\.\s+)?"  # noqa: RUF001
    r"(?:[A-ZÀ-Þ][\w ,&'’\-]*:\s*)?"  # noqa: RUF001
    r"[A-ZÀ-Þ][\w ,&'’\-]*[,.]\s*(?P<year>\d{4})(?:[–—-]\d{2,4})?\.?\s*$"  # noqa: RUF001
)
_HEAD_YEAR = re.compile(r"^\d{4}\.\s")
_ANY_YEAR = re.compile(r"\b\d{4}\b")

# How many hits it takes to trust a signal at all, how much a notes-style
# reading must outweigh an author-date one, and what fraction of the whole
# entry list the signal has to actually cover before the style counts as
# confirmed. Coverage matters as much as the ratio: a second real corpus
# (Couliano's *Tree of Gnosis* — natural-order first authors, a
# "(Place: Publisher, Year)." parenthetical instead of a bare tail year,
# same-author continuation marked "--" rather than an em dash) parsed only
# 5 of 288 entries at all, and every one of those 5 happened to read as
# tail-year — clearing the absolute _MIN_SAMPLE count on pure noise while
# 283 entries went unmeasured. tail_year / len(entries) was 63.9% for this
# module's one validated corpus and 1.7% for that one; the ratio among only
# the entries that parsed was ~99% for both and so cannot tell them apart —
# coverage is the signal that does.
_MIN_SAMPLE = 5
_CONFIRM_RATIO = 2
_MIN_COVERAGE = 0.3


@dataclass
class DocStyle:
    """What Pass 0 could confirm about this bibliography's own conventions.

    ``recognized`` gates the whole parser: this project can only validate
    a parser against the one style its corpus actually contains
    (Chicago/SBL notes-bibliography, year at the entry's tail). Anything
    sniffed as different — author-date's year immediately after the
    author, or no confirmed pattern at all — abstains rather than
    guessing at a shape nothing here has been tested against.
    """

    recognized: bool
    continuation_char: str | None = None
    continuation_count: int | None = None


@dataclass
class BibliographyEntry:
    """One reference entry, parsed as far as its shape allows.

    ``authors`` is always in "Surname, Given Names" written form — no
    attempt is made to normalise name order, since sigla resolution only
    ever needs to match a name as this corpus's own footnotes write it.
    ``role`` is the entry's own relationship to the work when that isn't
    plain authorship ("ed", "eds") — an editor's names still belong in
    ``authors`` (the edited volume's own citation identity), just tagged.
    A "Pausanias, trans. X" entry is different in kind, not degree: the
    translator isn't *any* kind of author of the work, so that name goes
    in ``translator`` instead of ``authors`` — leaving ``authors`` empty
    for such an entry rather than misattributing the work to whoever
    happened to translate it.
    """

    text: str
    authors: list[str] = field(default_factory=list)
    role: str | None = None
    title: str | None = None
    container: str | None = None
    editors: list[str] = field(default_factory=list)
    translator: list[str] = field(default_factory=list)
    year: str | None = None
    pages: str | None = None
    is_primary_source: bool = False


def sniff_style(entries: list[RawEntry]) -> DocStyle:
    """Confirm (never assume) the notes-bibliography, year-at-tail shape this parser knows.

    Two signals, each measured against ``entries`` rather than asserted:
    where the year falls relative to the author — at the tail (notes
    style, what this parser handles) or immediately after the author
    (author-date, which would silently break every end-anchored pattern
    below) — and which character, repeated how many times, this document's
    own same-author continuation marker actually uses (see
    ``_LEADING_DASH_RUN``'s docstring — never assumed to be an em dash, let
    alone three of them). Confirmation needs both an absolute count and
    *coverage*: an entry ``_parse_authors`` couldn't touch at all is
    skipped rather than counted against either signal, so an absolute
    threshold alone can clear on a handful of accidental matches while
    most of the bibliography goes unmeasured — exactly what happened
    against a second real corpus this style doesn't fit (see
    ``_MIN_COVERAGE``).
    """
    head_year = 0
    tail_year = 0
    dash_counts: Counter[tuple[str, int]] = Counter()
    for raw in entries:
        text = raw.text.replace(_ZWS, "")
        if m := _LEADING_DASH_RUN.match(text):
            dash_counts[(m.group("char"), len(m.group(0)) - 1)] += 1
            continue
        authors, rest = _parse_authors(text)
        if authors is None:
            continue
        if role_match := _ROLE.match(rest):
            rest = rest[role_match.end() :]
        if _HEAD_YEAR.match(rest):
            head_year += 1
        elif _ANY_YEAR.search(rest):
            tail_year += 1
    recognized = (
        bool(entries)
        and tail_year >= _MIN_SAMPLE
        and tail_year > head_year * _CONFIRM_RATIO
        and tail_year / len(entries) >= _MIN_COVERAGE
    )
    if dash_counts:
        (continuation_char, continuation_count), _ = dash_counts.most_common(1)[0]
    else:
        continuation_char = continuation_count = None
    return DocStyle(
        recognized=recognized,
        continuation_char=continuation_char,
        continuation_count=continuation_count,
    )


def parse_bibliography(entries: list[RawEntry], style: DocStyle) -> list[BibliographyEntry]:
    """Parse a section's raw, geometry-segmented entries into structure.

    Every entry falls back to raw ``text`` when ``style.recognized`` is
    False — an unconfirmed style gets no benefit of the doubt. Continuation
    entries resolve against the immediately preceding entry's name, since
    same-author continuations are always adjacent in a properly sorted
    bibliography — no lookback beyond one entry is ever needed. That name
    carries forward regardless of whether the previous entry used it as
    an author or a translator; which one *this* entry files it under is
    decided fresh each time, from this entry's own role marker.
    """
    if not style.recognized:
        return [BibliographyEntry(text=raw.text) for raw in entries]
    if style.continuation_char and style.continuation_count:
        continuation = _continuation_pattern(style.continuation_char, style.continuation_count)
    else:
        # No continuation marker sniffed at all — nothing to strip, rather
        # than guess at a character this document never showed.
        continuation = re.compile(r"(?!)")
    parsed: list[BibliographyEntry] = []
    previous_name: list[str] = []
    for raw in entries:
        entry = _parse_entry(raw.text, previous_name, continuation)
        parsed.append(entry)
        previous_name = entry.authors or entry.translator or previous_name
    classify_sources(parsed)
    return parsed


# Ancient-text series abbreviations, verified against this corpus's own
# bibliography rather than assumed from a style guide's general list: other
# candidates ("SC", "CCSL", "CSEL", "GCS", "TTH", "Nag Hammadi and Manichaean
# Studies") were checked and either don't appear here at all or — Nag
# Hammadi's own case — only ever show up in a modern secondary monograph's
# own series credit, not a primary edition. Grown by the same rule as
# `classical.py`'s sigla table: only what a real corpus has actually shown
# to discriminate correctly.
_PRIMARY_SERIES = re.compile(r"\bLCL\b|Loeb Classical Library|Ancient Christian Writers")
# A modern edition/translation apparatus, checked as raw text rather than
# via the structured ``translator``/``editors`` fields: those fields are
# only populated for specific entry shapes (a role marker at the very
# front, or a "Pages X in ... Edited by Y" chapter clause), but "Translated
# by Earnest Cary" sits mid-entry, describing who rendered an ancient
# author's *own* work into English — a fact this apparatus check needs
# regardless of whether the structured fields happened to capture it.
_APPARATUS = re.compile(r"\b(?:Translated|Edited)\s+by\b", re.IGNORECASE)


def classify_sources(entries: list[BibliographyEntry]) -> None:
    """Classify each entry primary (ancient) vs. secondary (modern), in place.

    HEU feature scoring, not identity resolution: this never asks *which*
    ancient author or work an entry names — that boundary belongs to
    `classical.py`'s own sigla table, and is exactly where a cheap
    classifier (or model) would start hallucinating. It only asks whether
    the entry's own shape reads as ancient, from independent structural
    signals, weighted so no single weak one decides alone:

    - the entry has a ``translator`` at all — "Van der Horst, Pieter
      Willem, trans. Chaeremon..." fronts a modern name, but the entry is
      still presenting someone else's work as a translation rather than
      authoring its own; ``authors`` is empty for exactly these entries
      (see ``BibliographyEntry``), so this signal is the only thing that
      still marks them as worth a closer look. Strong enough alone.
    - the entry's first author carries no comma at all — an ancient
      author cited by their own bare or natural name ("Cassius Dio", "The
      Apostolic Fathers") rather than the inverted "Surname, First" every
      modern scholar in this bibliography gets alphabetised by. **Not**
      strong enough alone, despite every bare-name entry in this
      project's first validated corpus also carrying edition apparatus
      (below) — a second real corpus (Couliano's *Eros and Magic*) showed
      two entries, "Faust. Cahiers de l'Hermétisme..." and "Soleil. Le
      Soleil à la Renaissance...", where a bare capitalized word is
      actually the print bibliography's own filing keyword for an
      anonymous themed collection, not a person. Needs the apparatus
      signal below to count.
    - a known ancient-text series (LCL, Loeb Classical Library, Ancient
      Christian Writers) or a "Translated by"/"Edited by" credit turns up
      in the entry's own text — corroborates the bare-name signal (every
      genuine bare-name entry in both validated corpora carries one or
      the other, since an ancient text only reaches a modern bibliography
      through a modern edition or translation), but never qualifies an
      entry alone: a modern scholar's own essay can appear *inside* one of
      these series' volumes (this corpus has exactly that case: an
      "Introduction" essay in a Loeb-adjacent edition, correctly left
      secondary here).

    An entry the parser couldn't resolve at all (no authors, no
    translator) is always left secondary rather than guessed, the same
    "don't guess with false confidence" rule this project applies
    everywhere else.
    """
    for entry in entries:
        bare_name = bool(entry.authors) and "," not in entry.authors[0]
        apparatus = bool(_APPARATUS.search(entry.text)) or bool(_PRIMARY_SERIES.search(entry.text))
        entry.is_primary_source = bool(entry.translator) or (bare_name and apparatus)


def _continuation_pattern(char: str, count: int) -> re.Pattern[str]:
    escaped = re.escape(char)
    return re.compile(rf"^(?:{escaped}{_ZWS}?){{{count}}}[.,:]?\s*")


def _parse_entry(
    raw_text: str, previous_name: list[str], continuation: re.Pattern[str]
) -> BibliographyEntry:
    text = raw_text.replace(_ZWS, "")
    if m := continuation.match(text):
        authors = previous_name
        rest = text[m.end() :]
    else:
        authors, rest = _parse_authors(text)
        if authors is None:
            return BibliographyEntry(text=raw_text)

    role = None
    translator: list[str] = []
    if m := _ROLE.match(rest):
        role = m.group(1)
        rest = rest[m.end() :]
        if role == "trans":
            # The translator isn't any kind of author of the work being
            # cited ("Van der Horst, Pieter Willem, trans. Chaeremon...");
            # the actual ancient author, if named at all, is embedded in
            # the title instead — leave ``authors`` empty rather than
            # attribute the work to whoever happened to translate it.
            translator, authors = authors, []
            role = None

    entry = BibliographyEntry(text=raw_text, authors=authors, role=role, translator=translator)
    if rest.startswith(_QUOTE_OPEN):
        close = rest.find(_QUOTE_CLOSE)
        if close == -1:
            return entry
        entry.title = rest[len(_QUOTE_OPEN) : close]
        tail = rest[close + 1 :].strip()
        if m := _YEAR_IN_PARENS.search(tail):
            entry.year = m.group("year")
            entry.container = tail[: m.start()].strip()
            if pages := _PAGES_AFTER_COLON.search(tail[m.end() :]):
                entry.pages = _clean_pages(pages.group("pages"))
        elif m := _CHAPTER_IN.match(tail):
            entry.pages = _clean_pages(m.group("pages"))
            after_in = tail[m.end() :]
            if intro := _EDITED_BY_INTRO.search(after_in):
                entry.container = after_in[: intro.start()].rstrip(". ")
                entry.editors, _ = _consume_editor_list(after_in[intro.end() :])
            elif book_tail := _BOOK_TAIL.search(after_in):
                entry.container = after_in[: book_tail.start()].rstrip(". ")
            else:
                entry.container = after_in.rstrip(". ")
            if year := _LAST_YEAR.search(tail):
                entry.year = year.group("year")
        elif year := _LAST_YEAR.search(tail):
            entry.year = year.group("year")
    else:
        if m := _BOOK_TAIL.search(rest):
            entry.title = rest[: m.start()].rstrip(". ")
            entry.year = m.group("year")
        else:
            entry.title = rest.rstrip(". ")
    return entry


def _parse_authors(text: str) -> tuple[list[str] | None, str]:
    """The author list at the start of an entry, and what's left after it.

    The first author is inverted ("Surname, First M."); the first comma
    is theirs. Later authors, if any, are natural order ("First M.
    Last"), each introduced by its own ", " or ", and ", until one is
    followed by the entry's own period rather than another comma.

    A primary source cited by its own name carries no comma before its
    name ends — "Cassius Dio. Roman History. Translated by..." — since
    an ancient author doesn't get alphabetised the way a modern
    scholar's surname does; the entry's *first* comma, if any, is off in
    its publication clause instead. Tried whenever the name's own period
    comes first, since these are exactly the entries a citation-dictation
    system most needs to recognise as primary sources.
    """
    comma = text.find(", ")
    period = text.find(". ")
    if comma == -1 or (period != -1 and period < comma):
        return _parse_bare_name(text)
    surname = text[:comma]
    rest = text[comma + 2 :]
    given, end = _consume_given_names(rest, _valid_after_author)
    if given is None:
        return None, text
    more = given.rstrip().endswith(",")
    authors = [f"{surname}, {given.strip().rstrip(',')}"]
    rest = rest[end:]
    while more:
        m = re.match(r"^and\s+", rest)
        skip = m.end() if m else 0
        person, consumed = _consume_natural_name(rest[skip:])
        if person is None:
            break
        authors.append(person)
        rest = rest[skip + consumed :]
        m = re.match(r"^,\s*(?:and\s+)?|^\.\s*", rest)
        if not m:
            break
        more = rest[: m.end()].lstrip().startswith(",")
        rest = rest[m.end() :]
    return authors, rest


def _parse_bare_name(text: str) -> tuple[list[str] | None, str]:
    """A primary source cited by its own name, no inverted surname at all.

    "Cassius Dio.", "Josephus.", "Tacitus." — one to a few capitalized
    words ended by the entry's own period, accepted only when what
    follows still validates as a plausible continuation.
    """
    pos = 0
    tokens = 0
    while pos < len(text) and tokens < 4:
        m = _GIVEN_TOKEN_RE.match(text, pos)
        if not m:
            break
        pos = m.end()
        tokens += 1
        if pos < len(text) and text[pos] == " " and _GIVEN_TOKEN_RE.match(text, pos + 1):
            pos += 1
            continue
        break
    if pos == 0 or not (pos < len(text) and text[pos] == "."):
        return None, text
    name = text[:pos]
    rest = text[pos + 1 :].lstrip()
    if not _valid_after_author(rest):
        return None, text
    return [name], rest


def _valid_after_author(rest: str) -> bool:
    """Does ``rest`` look like what can genuinely follow an author segment.

    Another author (natural order), a role ("ed.", "eds.", "trans."), a
    quoted article/chapter title, or — the only check with no local
    shape to match — a book title, accepted whenever *something* in
    ``rest`` still reads as a plausible publication tail.
    """
    if rest.startswith(_QUOTE_OPEN) or re.match(r"^(?:and\s+)?(?:eds?|trans)\.", rest):
        return True
    after_and = re.match(r"^and\s+", rest)
    if _consume_natural_name(rest[after_and.end() if after_and else 0 :])[0] is not None:
        return True
    return bool(_BOOK_TAIL.search(rest) or _LAST_YEAR.search(rest))


def _consume_given_names(text: str, validate) -> tuple[str | None, int]:
    """A given-name run, backtracking to whichever candidate ``validate`` accepts.

    Terminates at a comma (another author follows) or a period (a role
    or title follows) — at most two spelled words with any number of
    bare initials between or around them, matching every author name
    this corpus's bibliography actually uses. An initial followed by a
    capitalized word is structurally identical whether that word is a
    spelled middle name ("Harrill, J. Albert.") or the first word of a
    title ("Andrade, Nathanael J. Syrian Identity...") or the next
    author's name ("Beard, Mary, John A. North...") — nothing local
    tells these apart, only whether what's left validates afterward, so
    every plausible stopping point is tried, longest first.
    """
    candidates: list[int] = []
    pos = 0
    spelled = 0
    while pos < len(text) and len(candidates) < 4:
        if m := _INITIAL_RE.match(text, pos):
            pos = m.end()
        elif spelled < 2 and (m := _SPELLED_RE.match(text, pos)):
            pos = m.end()
            spelled += 1
        else:
            break
        end = None
        if pos < len(text) and text[pos] in ".,":
            end = pos + 1
        elif text[:pos].endswith("."):
            end = pos
        if end is not None:
            if end < len(text) and text[end] == " ":
                end += 1
            candidates.append(end)
        if pos < len(text) and text[pos] == " ":
            pos += 1
        else:
            break
    for end in reversed(candidates):
        if validate(text[end:]):
            return text[:end], end
    return None, 0


def _consume_natural_name(text: str) -> tuple[str | None, int]:
    """A natural-order name: "Philip A. Harland", "John S. Kloppenborg".

    Unlike the inverted first author, there's no closing-period
    ambiguity to resolve here: the name simply runs until the next token
    doesn't look like part of one, since a comma or the entry's own
    period — never a bare space — always separates it from what follows.
    """
    pos = 0
    tokens = 0
    while pos < len(text) and tokens < 5:
        m = _GIVEN_TOKEN_RE.match(text, pos)
        if not m:
            break
        pos = m.end()
        tokens += 1
        if pos < len(text) and text[pos] == " " and _GIVEN_TOKEN_RE.match(text, pos + 1):
            pos += 1
            continue
        break
    if tokens < 2:
        return None, 0
    return text[:pos], pos


def _consume_editor_list(text: str) -> tuple[list[str], int]:
    """One or more natural-order editor names, comma/and-separated.

    Reuses ``_consume_natural_name`` rather than splitting on commas
    textually, for the same reason the author list does: an editor's own
    initials ("Paul G. P. Meyboom") aren't reliably distinguishable from
    a name boundary by punctuation alone.
    """
    names: list[str] = []
    pos = 0
    while True:
        if m := re.match(r"^(?:,\s*)?(?:and\s+)?", text[pos:]):
            pos += m.end()
        person, consumed = _consume_natural_name(text[pos:])
        if person is None:
            break
        names.append(person)
        pos += consumed
        if pos < len(text) and text[pos] == ",":
            continue
        break
    return names, pos


def _clean_pages(pages: str) -> str:
    return re.sub(r"\s+", "", pages).rstrip(".")
