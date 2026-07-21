"""Speak citation abbreviations aloud — see ``base.py`` for the how and why.

One file per system (``biblical.py``, ``classical.py``, ``stephanus.py``,
``philo.py``, ``josephus.py``, and in time ``bekker.py``,
``diels_kranz.py``, unit systems); the engine that ties them together
lives in ``base.py``.
"""

from redaction.elocution.base import Elocutor, System, mechanical_locator
from redaction.elocution.biblical import BIBLICAL_SIGLA, biblical_system
from redaction.elocution.classical import CLASSICAL_SIGLA, classical_system
from redaction.elocution.josephus import JOSEPHUS_SIGLA, josephus_system
from redaction.elocution.philo import PHILO_SIGLA, philo_system
from redaction.elocution.stephanus import STEPHANUS_SIGLA, stephanus_system

__all__ = [
    "BIBLICAL_SIGLA",
    "CLASSICAL_SIGLA",
    "JOSEPHUS_SIGLA",
    "PHILO_SIGLA",
    "STEPHANUS_SIGLA",
    "Elocutor",
    "System",
    "biblical_system",
    "classical_system",
    "default_systems",
    "josephus_system",
    "mechanical_locator",
    "philo_system",
    "stephanus_system",
]


def default_systems() -> tuple[System, ...]:
    """The systems that run without any flag: fully deterministic, free.

    Order matters only for sigla identical across systems (see
    ``base.py``'s ``_merge``) — classical goes first so its "Num" (Numa)
    wins over biblical's "Num" (Numbers) in this corpus. Stephanus,
    Philo, and Josephus don't currently collide with the others or each
    other, so their position is arbitrary. Grows as Bekker/Diels-Kranz
    systems land.
    """
    return (
        classical_system(),
        stephanus_system(),
        philo_system(),
        josephus_system(),
        biblical_system(),
    )
