"""Classical author-work sigla — open vocabulary, grown via canon.py's two tiers.

Unlike the closed, universal biblical book sigla, Latin author-work
abbreviations ("Or." for an Oration, "Ann." for Tacitus's *Annals*) are a
large, heterogeneous vocabulary no one sitting still could enumerate once.
``CLASSICAL_SIGLA`` below holds one hand-verified seed entry, added for a
real collision rather than drafted: "Num" for Plutarch's *Numa*, confirmed
against ``temple_gates/sections/`` (Plutarch's Lives are cited by subject,
not "Life of X"). It shares its siglum with the biblical book of Numbers
(``biblical.py``); classical is listed first in ``default_systems()`` so
this entry wins that tie (see ``base.py``'s ``_merge``) — Numbers stays in
the biblical table for other corpora that do cite it.

Growth beyond that seed happens externally, in ``canon.py``'s two tiers —
a shared, hand-curated canon this machine keeps across every book, and a
per-document file for one book's own entries — rather than by hand-editing
this module further; see ``canon.py`` for why (TOML's comments for the
former, an eventual ``--elocution-draft`` sweep for the latter).
"""

from pathlib import Path

from redaction.elocution.base import System
from redaction.elocution.canon import merged_sigla

CLASSICAL_SIGLA: dict[str, str] = {
    "Num": "Numa",
}


def classical_system(elocution_dir: Path | None = None, directory: Path | None = None) -> System:
    return System("classical", merged_sigla(CLASSICAL_SIGLA, elocution_dir, directory, "classical"))
