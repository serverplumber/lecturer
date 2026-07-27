"""Diels-Kranz numbering — the standard citation scheme for the Presocratics.

Hermann Diels' *Die Fragmente der Vorsokratiker* (revised by Walther Kranz)
assigns each Presocratic philosopher a chapter number, splits it into A
(testimonia) and B (fragments), and numbers items within each; "DK 31 B112"
names Empedocles' fragment 112. Unlike biblical or Stephanus, there's no
sigla *table* to transcribe here — one abbreviation, "DK", covers every
philosopher, since the chapter number itself (not a per-author siglum) does
the identifying work. The locator shape ("31 B112", a chapter, a letter, an
item number) is different enough from the default dotted locator that this
system supplies its own — see ``base.py``'s
``DIELS_KRANZ_LOCATOR``/``diels_kranz_locator``.

Confirmed against real citations in Kingsley's *Ancient Philosophy, Mystery,
and Magic* (24 hits, e.g. "DK 31 B112", "DK 54 A2") rather than assumed.

TODO(serverplumber): 3 of those 24 don't convert, left untouched rather
than mangled — decide whether any are worth chasing:
- "DK47A1" — no space anywhere between siglum and locator. Structural, not
  a data gap: ``_merge``'s siglum/locator separator requires a literal
  space (deliberately, elsewhere, to stop a match bleeding across a
  paragraph break), so this can't match under the shared engine as it
  stands.
- "DK 21 Bag", "DK 87 B6o" — OCR digit/letter confusion (a fragment number
  misread as letters). Correctly inert rather than garbled: nothing here
  extends the match to a word boundary, so the whole citation is left as
  literal text instead of half-converting.
"""

from redaction.elocution.base import DIELS_KRANZ_LOCATOR, System, diels_kranz_locator

DIELS_KRANZ_SIGLA: dict[str, str] = {
    "DK": "Diels-Kranz",
}


def diels_kranz_system() -> System:
    return System(
        "diels_kranz",
        DIELS_KRANZ_SIGLA,
        locator=DIELS_KRANZ_LOCATOR,
        speak_locator=diels_kranz_locator,
    )
