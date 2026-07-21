"""Josephus — closed, standard, no draft needed.

Verified against the SBL Handbook's §8.3.7, which lists Josephus
separately from the general classical/patristic table since (like Philo)
his corpus gets its own dedicated section. SBL gives both a Latin-style
siglum and an English-style one for each work and treats either as
legitimate — both are included here, plus the period-less forms ("AJ",
"BJ") this corpus's own bibliography actually uses (quoting an article
title verbatim: "Josephus, AJ 1.154-68"), alongside "Ant." which the
corpus's own footnote prose uses directly ("Josephus, Ant. 1.154-68").
Shares the general dotted book.section locator.

"Vita"/"Life" for the autobiography: only "Vita" is included. Bare
"Life" is far too common an English word to risk as a citation siglum —
the numeric-locator requirement immediately after guards most sigla
well enough, but not one this generic.
"""

from redaction.elocution.base import System

JOSEPHUS_SIGLA: dict[str, str] = {
    "Vita": "Life",
    "C. Ap": "Against Apion",
    "Ag. Ap": "Against Apion",
    "A.J": "Jewish Antiquities",
    "AJ": "Jewish Antiquities",
    "Ant": "Jewish Antiquities",
    "B.J": "Jewish War",
    "BJ": "Jewish War",
    "J.W": "Jewish War",
    "JW": "Jewish War",
}


def josephus_system() -> System:
    return System("josephus", JOSEPHUS_SIGLA)
