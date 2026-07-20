"""Classical author-work sigla — open vocabulary, eventually LLM-drafted.

Unlike the closed, universal biblical book sigla, Latin author-work
abbreviations ("Or." for an Oration, "Ann." for Tacitus's *Annals*) are a
large, heterogeneous, per-document vocabulary. The real version of this
table is meant to be populated by a per-document cheap-LLM draft sweep
into a hand-editable map — the ``--lexicon-draft`` *pattern*, not yet
built for this system.

For now this holds one hand-verified seed entry, added for a real
collision rather than drafted: "Num" for Plutarch's *Numa*, confirmed
against ``temple_gates/sections/`` (Plutarch's Lives are cited by
subject, not "Life of X"). It shares its siglum with the biblical book
of Numbers (``biblical.py``); classical is listed first in
``default_systems()`` so this entry wins that tie (see ``base.py``'s
``_merge``) — Numbers stays in the biblical table for other corpora that
do cite it.
"""

from redaction.elocution.base import System

CLASSICAL_SIGLA: dict[str, str] = {
    "Num": "Numa",
}


def classical_system() -> System:
    return System("classical", CLASSICAL_SIGLA)
