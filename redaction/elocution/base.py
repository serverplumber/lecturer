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
vocabulary, which is each system's own business (see ``biblical.py`` for
a closed, hardcoded one; open ones — classical author-work abbreviations,
and later Bekker, Diels-Kranz, Stephanus, unit systems — get a
hand-editable, LLM-drafted map instead, additive and never-overwriting,
on the lexicon-draft pattern).

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
from collections.abc import Callable, Mapping, Sequence
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
# subtraction.
_RANGE_DASH = "-–−"  # noqa: RUF001
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


# A locator: one to three dot/colon-separated numbers, optionally a range.
# "2:10", "2:10-12", "32.9.6-10" all match; the siglum table decides which
# sigla this ever gets tried against.
_LOCATOR = rf"\d+(?:[.:]\d+){{0,2}}(?:[{_RANGE_DASH}]\d+(?:[.:]\d+)?)?"


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
    locator: str = _LOCATOR
    speak_locator: Callable[[str], str] = mechanical_locator


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

    Sigla that are identical strings across systems (biblical's "Num" for
    Numbers, classical's "Num" for Plutarch's *Numa*) can't be told apart
    by length; those tie-break by priority, earlier systems in
    ``systems`` winning. A real "Num" citation for the other system, in a
    corpus that cites both, is the one case this can't get right — that
    needs context no siglum table carries.
    """
    seen: dict[str, _Entry] = {}
    for system in systems:
        for siglum, spoken in system.sigla.items():
            seen.setdefault(siglum, _Entry(siglum, spoken, system))
    entries = sorted(seen.values(), key=lambda entry: len(entry.siglum), reverse=True)
    if not entries:
        return re.compile(r"(?!)"), []
    branches = (
        rf"(?P<sig{i}>{re.escape(entry.siglum)})\.? (?P<loc{i}>{entry.system.locator})"
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
