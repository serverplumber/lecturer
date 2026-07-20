"""Speak citation abbreviations aloud — see ``base.py`` for the how and why.

One file per system (``biblical.py``, ``classical.py``, and in time
``bekker.py``, ``diels_kranz.py``, ``stephanus.py``, unit systems); the
engine that ties them together lives in ``base.py``.
"""

from redaction.elocution.base import Elocutor, System, mechanical_locator
from redaction.elocution.biblical import BIBLICAL_SIGLA, biblical_system
from redaction.elocution.classical import CLASSICAL_SIGLA, classical_system

__all__ = [
    "BIBLICAL_SIGLA",
    "CLASSICAL_SIGLA",
    "Elocutor",
    "System",
    "biblical_system",
    "classical_system",
    "default_systems",
    "mechanical_locator",
]


def default_systems() -> tuple[System, ...]:
    """The systems that run without any flag: fully deterministic, free.

    Order matters only for sigla identical across systems (see
    ``base.py``'s ``_merge``) — classical goes first so its "Num" (Numa)
    wins over biblical's "Num" (Numbers) in this corpus. Grows as
    Bekker/Diels-Kranz/Stephanus systems land.
    """
    return (classical_system(), biblical_system())
