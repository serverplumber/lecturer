"""Stephanus pagination — Plato's dialogues, closed and standard, no draft needed.

Henri Estienne's 1578 edition of Plato assigned each page a number and
divided it into five lettered sections (a-e); every modern edition prints
those numbers in the margin, and scholarship cites Plato by them instead
of any edition's own page numbers. Like the biblical canon, the dialogue
list is small, fixed, and universally known: hardcoded rather than
drafted. The locator shape ("364b", "514a2", a page-letter-line, optionally
a range) is different enough from ``System``'s default dotted
chapter.section locator that this system supplies its own — see
``base.py``'s ``STEPHANUS_LOCATOR``/``stephanus_locator``.

Verified against the SBL Handbook's own table (§8.3.14.3, which lists
Plato among the classical authors): sigla and spoken forms below are
SBL's, not memory-recalled guesses — a first pass at this table (since
replaced) had "Stat" for *Statesman* where SBL actually prescribes "Pol"
(Politicus), "Euthyph" where SBL has "Euthyphr", and included several
dialogues ("Ion", "Lysis", "Meno", "Crito", "Critias") that SBL's table
doesn't cover at all. Bracketed entries in SBL (`[Alc. maj.]`,
`[Epin.]`, `[Min.]`) mark works of disputed authorship, still real
citable forms; the brackets themselves are apparatus, not spoken.

"Ep" (Epistulae, Plato's *Letters*) is deliberately omitted: SBL's own
rules (§8.3.14.1, rule 11) list "ep." among abbreviations reused
identically across many different authors' letter collections, so
attributing a bare "Ep." to Plato specifically would be a guess this
system can't safely make without the author-name context it doesn't
carry. Left unresolved is safer than resolved wrong.

Some dialogues here overlap literally with other systems' sigla ("Apol."
is also a natural siglum for a patristic Apology) but not in locator
shape — a page+letter after "Apol." resolves here, a chapter.section
resolves elsewhere; see ``base.py``'s ``_merge`` for why both can be
listed without either shadowing the other.
"""

from redaction.elocution.base import STEPHANUS_LOCATOR, System, stephanus_locator

STEPHANUS_SIGLA: dict[str, str] = {
    "Alc. maj": "Greater Alcibiades",  # disputed authorship
    "Apol": "Apology",
    "Ax": "Axiochus",  # disputed authorship
    "Charm": "Charmides",
    "Crat": "Cratylus",
    "Def": "Definitions",  # disputed authorship
    "Euthyd": "Euthydemus",
    "Euthyphr": "Euthyphro",
    "Gorg": "Gorgias",
    "Hipparch": "Hipparchus",
    "Hipp. maj": "Greater Hippias",
    "Hipp. min": "Lesser Hippias",
    "Lach": "Laches",
    "Leg": "Laws",
    "Menex": "Menexenus",
    "Min": "Minos",  # disputed authorship
    "Parm": "Parmenides",
    "Phaed": "Phaedo",
    "Phaedr": "Phaedrus",
    "Phileb": "Philebus",
    "Pol": "Statesman",
    "Prot": "Protagoras",
    "Resp": "Republic",
    "Soph": "Sophist",
    "Symp": "Symposium",
    "Theaet": "Theaetetus",
    "Tim": "Timaeus",
}


def stephanus_system() -> System:
    return System(
        "stephanus", STEPHANUS_SIGLA, locator=STEPHANUS_LOCATOR, speak_locator=stephanus_locator
    )
