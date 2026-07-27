"""Qumran document numbering — SBL §8.3.5, a generative shape, not a table.

A Dead Sea Scroll from Qumran is named by cave and document number: "4Q246"
is the document catalogued 246th from Cave 4. Eleven caves, hundreds of
numbered documents in each — there's no finite siglum table to transcribe
the way there is for biblical books or Plato's dialogues, so this is a
``PatternSystem``: the citation shape is matched directly and its spoken
form ("four Q, two-four-six" — digit-by-digit, call-sign style, not a
cardinal number) is computed by parsing the match, not looked up — see
``base.py``'s ``QUMRAN_PATTERN``/``speak_qumran``,
alongside ``STEPHANUS_LOCATOR``/``stephanus_locator`` and
``DIELS_KRANZ_LOCATOR``/``diels_kranz_locator`` for the same reason those
live in the engine module rather than here: this file, like ``stephanus.py``
and ``diels_kranz.py``, holds only what's specific to the scheme.

Scoped to the bare numbered form only ("4Q246", "11Q13"), confirmed against
105 real citations across Collins' *The Apocalyptic Imagination* and
deClaisse-Walford's *The Shape and Shaping of the Psalter* — almost always
cited standalone, with no locator at all ("4Q177, 4Q280, and 4Q286"), which
is why ``QUMRAN_PATTERN`` matches a whole citation rather than splitting a
siglum from a locator the way every table-driven system here does.

Two real shapes deliberately not covered yet:

- **Named/lettered documents** ("1QH", "4QMMT", "11QPsa" — a cave, a Q, an
  abbreviated document name, sometimes a copy-letter glued on with no
  separator for "the a-copy of Psalms"). These need a spoken form for the
  name component, and unlike the bare number, there's no way to compute
  one mechanically — "Psa" isn't a number to spell. That needs a design
  decision (spell the letters? a per-document lookup?) before it can be
  built, not a data gap this file can quietly fill in.
- **CD** (the Cairo Genizah Damascus Document) — a fixed, closed siglum
  with no cave number at all, genuinely table-shaped rather than
  pattern-shaped; it belongs in a regular ``System`` once it's worth
  building, not folded into this file's generative pattern.

Both of the above, when they do take a locator, use the plain colon
grammar already built (``base.py``'s default ``LOCATOR``) — confirmed
against real citations ("1QH 11:19-22", "CD 12:23-13:1"); the gap is only
the siglum side.
"""

from redaction.elocution.base import QUMRAN_PATTERN, PatternSystem, speak_qumran


def qumran_system() -> PatternSystem:
    return PatternSystem("qumran", QUMRAN_PATTERN, speak_qumran)
