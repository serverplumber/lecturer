"""Speak citation abbreviations aloud — see ``base.py`` for the how and why.

One file per system (``biblical.py``, ``classical.py``, ``stephanus.py``,
``philo.py``, ``josephus.py``, ``bare_authors.py``, ``diels_kranz.py``,
``pseudepigrapha.py``, ``qumran.py``, and in time ``bekker.py``, unit
systems); the engine that ties them together lives in ``base.py``.
"""

from redaction.elocution.bare_authors import BARE_AUTHORS, bare_authors_system
from redaction.elocution.base import (
    Elocutor,
    PatternSystem,
    System,
    bare_author_system,
    mechanical_locator,
)
from redaction.elocution.biblical import BIBLICAL_SIGLA, biblical_system
from redaction.elocution.classical import CLASSICAL_SIGLA, classical_system
from redaction.elocution.diels_kranz import DIELS_KRANZ_SIGLA, diels_kranz_system
from redaction.elocution.josephus import JOSEPHUS_SIGLA, josephus_system
from redaction.elocution.philo import PHILO_SIGLA, philo_system
from redaction.elocution.pseudepigrapha import PSEUDEPIGRAPHA_SIGLA, pseudepigrapha_system
from redaction.elocution.qumran import CD_SIGLA, damascus_document_system, qumran_system
from redaction.elocution.stephanus import STEPHANUS_SIGLA, stephanus_system

__all__ = [
    "BARE_AUTHORS",
    "BIBLICAL_SIGLA",
    "CD_SIGLA",
    "CLASSICAL_SIGLA",
    "DIELS_KRANZ_SIGLA",
    "JOSEPHUS_SIGLA",
    "PHILO_SIGLA",
    "PSEUDEPIGRAPHA_SIGLA",
    "STEPHANUS_SIGLA",
    "Elocutor",
    "PatternSystem",
    "System",
    "bare_author_system",
    "bare_authors_system",
    "biblical_system",
    "classical_system",
    "damascus_document_system",
    "default_systems",
    "diels_kranz_system",
    "josephus_system",
    "mechanical_locator",
    "philo_system",
    "pseudepigrapha_system",
    "qumran_system",
    "stephanus_system",
]


def default_systems() -> tuple[System | PatternSystem, ...]:
    """The systems that run without any flag: fully deterministic, free.

    Order matters only for sigla identical across systems (see
    ``base.py``'s ``_merge``) — classical goes first so its "Num" (Numa)
    wins over biblical's "Num" (Numbers) in this corpus. Stephanus, Philo,
    Josephus, Diels-Kranz, pseudepigrapha, Qumran, the Damascus Document,
    and the bare-author list don't currently collide with the others or
    each other, so their position is arbitrary. Grows as Bekker lands.
    """
    return (
        classical_system(),
        stephanus_system(),
        philo_system(),
        josephus_system(),
        diels_kranz_system(),
        pseudepigrapha_system(),
        qumran_system(),
        damascus_document_system(),
        biblical_system(),
        bare_authors_system(),
    )
