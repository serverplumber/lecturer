"""Speak citation abbreviations aloud — see ``base.py`` for the how and why.

One file per system (``biblical.py``, ``classical.py``, ``stephanus.py``,
and in time ``bekker.py``, ``diels_kranz.py``, unit systems); the engine
that ties them together lives in ``base.py``.
"""

from redaction.elocution.base import Elocutor, System, mechanical_locator
from redaction.elocution.biblical import BIBLICAL_SIGLA, biblical_system
from redaction.elocution.classical import CLASSICAL_SIGLA, classical_system
from redaction.elocution.stephanus import STEPHANUS_SIGLA, stephanus_system

__all__ = [
    "BIBLICAL_SIGLA",
    "CLASSICAL_SIGLA",
    "STEPHANUS_SIGLA",
    "Elocutor",
    "System",
    "biblical_system",
    "classical_system",
    "default_systems",
    "mechanical_locator",
    "stephanus_system",
]


def default_systems() -> tuple[System, ...]:
    """The systems that run without any flag: fully deterministic, free.

    Order matters only for sigla identical across systems (see
    ``base.py``'s ``_merge``) — classical goes first so its "Num" (Numa)
    wins over biblical's "Num" (Numbers) in this corpus. Stephanus's
    sigla don't currently collide with either, so its position among
    the three is arbitrary. Grows as Bekker/Diels-Kranz systems land.
    """
    return (classical_system(), stephanus_system(), biblical_system())
