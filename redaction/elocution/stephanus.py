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

Some dialogues here overlap literally with other systems' sigla ("Apol."
is also a natural siglum for a patristic Apology) but not in locator
shape — a page+letter after "Apol." resolves here, a chapter.section
resolves elsewhere; see ``base.py``'s ``_merge`` for why both can be
listed without either shadowing the other.
"""

from redaction.elocution.base import STEPHANUS_LOCATOR, System, stephanus_locator

STEPHANUS_SIGLA: dict[str, str] = {
    "Alcib. 1": "Alcibiades",
    "Alcib. 2": "Second Alcibiades",
    "Apol": "Apology",
    "Charm": "Charmides",
    "Crat": "Cratylus",
    "Criti": "Critias",
    "Crito": "Crito",
    "Epin": "Epinomis",
    "Euthyd": "Euthydemus",
    "Euthyph": "Euthyphro",
    "Gorg": "Gorgias",
    "Hipp. Maj": "Greater Hippias",
    "Hipp. Min": "Lesser Hippias",
    "Ion": "Ion",
    "Lach": "Laches",
    "Leg": "Laws",
    "Lysis": "Lysis",
    "Menex": "Menexenus",
    "Meno": "Meno",
    "Parm": "Parmenides",
    "Phaed": "Phaedo",
    "Phaedr": "Phaedrus",
    "Phileb": "Philebus",
    "Prot": "Protagoras",
    "Resp": "Republic",
    "Soph": "Sophist",
    "Stat": "Statesman",
    "Symp": "Symposium",
    "Theaet": "Theaetetus",
    "Tim": "Timaeus",
}


def stephanus_system() -> System:
    return System(
        "stephanus", STEPHANUS_SIGLA, locator=STEPHANUS_LOCATOR, speak_locator=stephanus_locator
    )
