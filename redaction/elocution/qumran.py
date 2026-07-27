"""Qumran document numbering — SBL §8.3.5, a generative shape, not a table.

A Dead Sea Scroll from Qumran is named by cave and document number: "4Q246"
is the document catalogued 246th from Cave 4. Eleven caves, hundreds of
numbered documents in each — there's no finite siglum table to transcribe
the way there is for biblical books or Plato's dialogues, so this is a
``PatternSystem``: the citation shape is matched directly and its spoken
form is computed by parsing the match, not looked up wholesale — see
``base.py``'s ``QUMRAN_PATTERN``/``speak_qumran``, alongside
``STEPHANUS_LOCATOR``/``stephanus_locator`` and
``DIELS_KRANZ_LOCATOR``/``diels_kranz_locator`` for the same reason those
live in the engine module rather than here: this file, like ``stephanus.py``
and ``diels_kranz.py``, holds only what's specific to the scheme.

A bare document number ("4Q246", "11Q13") is read digit-by-digit,
call-sign style ("four Q, two-four-six") — 105 real citations confirmed
across Collins' *The Apocalyptic Imagination* and deClaisse-Walford's *The
Shape and Shaping of the Psalter*, almost always cited standalone with no
locator at all ("4Q177, 4Q280, and 4Q286"). A *named* document ("1QH",
"4QMMT", "11QPsa") is looked up and spoken by name instead, the same as
any biblical book — ``base.py``'s ``QUMRAN_NAMES``, verified against
SBL's own English (or, where SBL gives none, its own Hebrew
transliteration) title, evidenced by real citations in Collins (1QH,
1QM, 1QS, 4QMMT) and deClaisse-Walford, whose whole subject is 11QPsa
(the "Ps" siglum, cited dozens of times with copy letters a-e). A
lowercase copy letter glued on with no separator ("11QPsa", "4Q98d" —
real DSS convention for "the a-copy") applies to either shape, spoken
capitalised, the same as Stephanus's page-letter — unlike Stephanus's own
fixed five (a-e), there's no fixed ceiling on how many copies of a work
might turn up, so the grammar allows any single lowercase letter rather
than a narrow evidenced range.

Both shapes, when they do take a locator, use the plain colon grammar
already built (``base.py``'s default ``LOCATOR``) — confirmed against
real citations ("1QH 11:19-22", "4QMMT 6:1").

``CD`` (the Cairo Genizah copy of the Damascus Document) has no cave
number at all — a fixed, closed siglum, genuinely table-shaped rather
than pattern-shaped, so it's a plain ``System`` here rather than folded
into the generative pattern; its own colon locator ("CD 12:23-13:1") is
already the default grammar, no custom locator needed.
"""

from redaction.elocution.base import QUMRAN_PATTERN, PatternSystem, System, speak_qumran

CD_SIGLA: dict[str, str] = {
    "CD": "the Damascus Document",
}


def qumran_system() -> PatternSystem:
    return PatternSystem("qumran", QUMRAN_PATTERN, speak_qumran)


def damascus_document_system() -> System:
    return System("damascus_document", CD_SIGLA)
