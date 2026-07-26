"""The system-agnostic engine: recognise a citation, speak its two halves.

A written citation like "1 Cor 2:10" or "Or. 32.9.6-10" reads fine on the
page and badly aloud: the TTS has no way to know "1 Cor" names a book
rather than a quantity, or that ":" and "-" separate locators rather than
mean subtraction and a range of magnitudes. Recognition splits in two,
matching how confident each half can be. The numeric locator is
mechanical regardless of system: spell each number, turn separators into
the words a reader would use ("2:10" -> "two, ten", "32.9.6-10" ->
"thirty-two, nine, six to ten") — book/chapter/section labels are
deliberately not inserted unless a sample proves the bare numbers
ambiguous, matching how these are actually read aloud. The siglum's
spoken form ("1 Cor" -> "First Corinthians", "Or." -> "Oration") needs a
vocabulary, which is each system's own business. Closed, universal,
enumerable ones (``biblical.py``, ``stephanus.py``, and in time Bekker,
Diels-Kranz) get a hardcoded table like this module's default locator;
open ones — classical author-work abbreviations, unit systems — get a
hand-editable, LLM-drafted map instead, additive and never-overwriting,
on the lexicon-draft pattern.

Each system's citations are matched against its own siglum table, so an
abbreviation not yet in the table simply never matches, rather than
matching and then guessing. Leaving it untouched until a draft sweep or
hand edit adds it beats pronouncing it wrong with false confidence.

All systems are matched in one combined pass, not one sequential pass
per system (see ``Elocutor``/``_merge``) — a separate pass per system
would let a later, narrower pattern's own independent scan claim a
substring that an earlier, wider citation should have owned whole.
"""

import re
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass

from redaction.base import Script, ScriptSection, Utterance

_ONES = (
    "zero",
    "one",
    "two",
    "three",
    "four",
    "five",
    "six",
    "seven",
    "eight",
    "nine",
    "ten",
    "eleven",
    "twelve",
    "thirteen",
    "fourteen",
    "fifteen",
    "sixteen",
    "seventeen",
    "eighteen",
    "nineteen",
)
_TENS = ("", "", "twenty", "thirty", "forty", "fifty", "sixty", "seventy", "eighty", "ninety")


def _spell(n: int) -> str:
    """A cardinal number in plain English words, for citation-sized locators."""
    if n < 20:
        return _ONES[n]
    if n < 100:
        tens, ones = divmod(n, 10)
        return _TENS[tens] + (f"-{_ONES[ones]}" if ones else "")
    if n < 1000:
        hundreds, rest = divmod(n, 100)
        return f"{_ONES[hundreds]} hundred" + (f" {_spell(rest)}" if rest else "")
    thousands, rest = divmod(n, 1000)
    return f"{_spell(thousands)} thousand" + (f" {_spell(rest)}" if rest else "")


# A range dash shows up as a plain hyphen, an en dash, or (this corpus's
# typesetting) a true Unicode minus sign — all three are "to" here, never
# subtraction. A zero-width space sometimes sits right after it (an EPUB
# hyphenation artifact seen in this corpus's footnotes, e.g. "364b" then the
# dash then a hidden character then "365a"): tolerated in the locator
# patterns below, and simply skipped here since it never matches any of
# these alternatives.
_RANGE_DASH = "-–−"  # noqa: RUF001
_ZWS = "\u200b"
_LOCATOR_TOKEN = re.compile(rf"\d+|[.:]|[{_RANGE_DASH}]")


def mechanical_locator(locator: str) -> str:
    """Spell out a locator's digits; separators become the words a reader says.

    Deliberately mechanical and label-free: which number means "chapter"
    versus "verse" is a per-system, per-work judgement this default does
    not make. A system that needs labels supplies its own ``speak_locator``.
    """
    pieces = []
    for token in _LOCATOR_TOKEN.finditer(locator):
        text = token.group(0)
        if text[0].isdigit():
            pieces.append(_spell(int(text)))
        elif text in _RANGE_DASH:
            pieces.append(" to ")
        else:  # "." or ":"
            pieces.append(", ")
    return "".join(pieces)


# A locator: one or more dot/colon-separated numbers, optionally a range.
# "2:10", "2:10-12", "32.9.6-10" all match; the siglum table decides which
# sigla this ever gets tried against. Not capped at three parts — real
# citations in this corpus go to four ("Livy, 13.16.8.1"), and nothing
# about the grammar depends on a fixed depth: the repeated group only ever
# continues onto a digit immediately after a "." or ":", so a genuine
# sentence break (period-then-space, or period-then-capital) still stops
# the match exactly where the old bounded version did. Public: this is the
# shared sub-grammar other elocution modules (e.g. ``citation_pairing.py``)
# import rather than duplicate.
LOCATOR = rf"\d+(?:[.:]\d+)*(?:[{_RANGE_DASH}]{_ZWS}?\d+(?:[.:]\d+)*)?"


_STEPHANUS_UNIT = r"\d+[a-e]\d*"
_STEPHANUS_UNIT_RE = re.compile(r"(\d+)([a-e])(\d*)")
# A Stephanus locator: a page number, section letter (a-e — the five parts
# Estienne's 1578 Plato divides each page into), optional line number,
# optionally a range to a second such unit. "364b", "514a2", "364b-365a".
STEPHANUS_LOCATOR = rf"{_STEPHANUS_UNIT}(?:[{_RANGE_DASH}]{_ZWS}?{_STEPHANUS_UNIT})?"


def stephanus_locator(locator: str) -> str:
    """Speak a Stephanus citation: page, section letter, optional line.

    "364b" -> "three hundred sixty-four B"; "364b-365a" -> "...to three
    hundred sixty-five A". The letter is capitalised so a TTS reads it as
    a letter name rather than the indefinite article.
    """
    pieces = []
    for unit in re.finditer(_STEPHANUS_UNIT, locator):
        if pieces:
            pieces.append(" to ")
        page, letter, line = _STEPHANUS_UNIT_RE.match(unit.group(0)).groups()
        piece = f"{_spell(int(page))} {letter.upper()}"
        if line:
            piece += f", {_spell(int(line))}"
        pieces.append(piece)
    return "".join(pieces)


@dataclass
class System:
    """One abbreviation system Elocutor can speak.

    ``locator`` is a regex fragment (no group of its own) for this
    system's numeric-locator shape; ``speak_locator`` renders a match of
    it in words. Both default to the generic mechanical scheme every
    system needs so far.
    """

    name: str
    sigla: Mapping[str, str]
    locator: str = LOCATOR
    speak_locator: Callable[[str], str] = mechanical_locator


def bare_author_system(authors: Iterable[str]) -> System:
    """A system for authors cited by name alone, with no work siglum at all.

    Most classical authors never get their own multi-work sigla table —
    SBL enumerates the ones that do (Josephus, Philo, Suetonius, ...),
    each because their body of distinct works needs disambiguating.
    Someone conventionally cited as having written one work is just
    named directly before the locator: "Cassius Dio, 57.25.8", "Livy,
    1.36.2-6". There's no abbreviation to expand, so this reuses the same
    matching and replacement machinery as every siglum table, just keyed
    by the author's own full name — the "siglum" is the name, and the
    "spoken form" is that name again, with the comma the source already
    puts there baked in, since ``_merge``'s comma-or-period separator is
    consumed by the match and would otherwise vanish from the spoken
    output, losing the pause a reader would actually say. That comma is
    added unconditionally, even where the source has none ("Livy 1.36.2"
    would still speak "Livy, one, thirty-six, two") — a deliberate
    choice, not a bug: every one of these citations wants that pause.
    """
    return System("bare_author", {name: f"{name}," for name in authors})


@dataclass
class _Entry:
    siglum: str
    spoken: str
    system: System


def _merge(systems: Sequence[System]) -> tuple[re.Pattern[str], list[_Entry]]:
    """One pattern for every system's citations, matched in a single scan.

    A sequential pass per system would let a later, narrower pattern's
    own independent scan match a substring an earlier, wider citation
    should have claimed whole: biblical's "2 Cor" versus a hypothetical
    classical "Cor." for Plutarch's *Coriolanus* would otherwise turn
    "2 Cor. 3.18" into "2 Coriolanus three, eighteen" — the "Cor." pass
    has no idea it is standing inside someone else's match. One merged,
    longest-siglum-first alternation lets the regex engine's own
    leftmost, non-overlapping scan settle that for free: "2 Cor" starts
    two characters before "Cor" could, so it is tried first and consumes
    the whole span before "Cor" ever gets a turn.

    Entries are never deduplicated by siglum text alone: two systems can
    legitimately share a written siglum with different locator shapes —
    Plato's "Apol." (Stephanus page+letter) versus a patristic "Apol."
    (chapter.section) — and since each is its own branch with its own
    locator sub-pattern, the regex engine's own alternation and
    backtracking sorts these out per citation: whichever branch's full
    siglum-plus-locator actually matches the text that follows wins, and
    a branch whose locator shape doesn't fit simply fails over to the
    next one at that position.

    That only works when the locator shapes differ enough to fail
    distinctly. Sigla that are identical strings *and* share a locator
    shape (biblical's "Num" for Numbers, classical's "Num" for Plutarch's
    *Numa*, both plain dotted numbers) are genuinely ambiguous; those
    tie-break by priority — earlier systems in ``systems`` win, since the
    sort below is stable and this function lists each system's entries
    in the order given before sorting by length. A real "Num" citation
    for the losing system, in a corpus that cites both, is the one case
    this can't get right — that needs context no siglum table carries.
    """
    entries = [
        _Entry(siglum, spoken, system)
        for system in systems
        for siglum, spoken in system.sigla.items()
    ]
    entries.sort(key=lambda entry: len(entry.siglum), reverse=True)
    if not entries:
        return re.compile(r"(?!)"), []
    # An abbreviation is followed by an optional period ("Num. 8.10") or
    # nothing at all ("1 Cor 2:10"); a bare author name cited with no
    # siglum ("Cassius Dio, 57.25.8", see ``bare_author_system``) is
    # followed by a comma instead — widened here rather than given its own
    # branch shape, since the separator is the only thing that differs.
    # A single literal space, not ``\s+``: extraction joins paragraphs with
    # blank lines, and ``\s+`` would let a siglum-shaped word ending one
    # paragraph match across the break into a locator-shaped number
    # starting the next.
    branches = (
        rf"(?P<sig{i}>{re.escape(entry.siglum)})[,.]? (?P<loc{i}>{entry.system.locator})"
        for i, entry in enumerate(entries)
    )
    return re.compile(rf"\b(?:{'|'.join(branches)})\b"), entries


class Elocutor:
    """Speak citation abbreviations aloud, every system in one combined pass.

    Ordered after the weaver and before ``LanguageTagger``/``Cantillator``:
    a woven-in note can itself carry citations, and Cantillator should
    see the final expanded prose rather than the unexpanded shorthand.
    """

    def __init__(self, systems: Sequence[System]) -> None:
        self.systems = systems
        self._pattern, self._entries = _merge(systems)

    def redact(self, script: Script) -> Script:
        return Script(
            sections=[
                ScriptSection(
                    title=section.title,
                    utterances=[
                        Utterance(
                            text=self._pattern.sub(self._replace, u.text),
                            manner=u.manner,
                            lang=u.lang,
                        )
                        for u in section.utterances
                    ],
                    footnotes=section.footnotes,
                )
                for section in script.sections
            ]
        )

    def _replace(self, match: re.Match[str]) -> str:
        index = int(match.lastgroup.removeprefix("loc"))
        entry = self._entries[index]
        return f"{entry.spoken} {entry.system.speak_locator(match.group(match.lastgroup))}"
