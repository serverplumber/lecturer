"""``draft-classical``: an LLM sweep that seeds classical.toml (tier 2).

``citation_pairing.py``'s ``pair_sigla`` already tells us, structurally,
which (author, siglum) pairs a document's own footnotes use — no guessing,
since the prose names the author right there ("Josephus, AJ 18.81-84").
What's still missing for a candidate like that is the siglum's spoken form
("AJ" -> "Jewish Antiquities"): a narrower ask than identity, since the
author side is already settled, but real judgement none of this project's
grep-only layers can supply. That's the one thing this module asks an LLM
for — exactly the boundary ``classical.py``'s own docstring and
``citation_pairing.py``'s were written to describe before either was built.

A candidate is a pairing whose siglum isn't already resolved by any system
in play (biblical, Stephanus, Philo, Josephus, Diels-Kranz, pseudepigrapha,
Qumran, the Damascus Document, bare authors, or classical's own two tiers —
covers Josephus/Philo's own dedicated tables without needing to special-case
them) and isn't flagged ambiguous by ``pair_sigla``'s own ``collisions()`` —
a siglum this document pairs with more than one author needs a human's eyes,
not a guess. Resolved entries land in tier 2 only (``canon.py``'s
``add_tier2``) — this document's ``classical.toml`` — never tier 1: an LLM's
guess isn't evidence until a human runs ``promote-classical`` to say so, the
same posture ``add_tier2``/``promote`` already hold.

A siglum that stays unresolved — genuinely ambiguous, or one the model
wasn't confident about — isn't just logged and forgotten: it's written into
``classical.toml`` as a stub (``canon.py``'s module docstring), with a
bibliography hint pulled from the document's own confirmed primary-source
entries where one names the author, so a human finds a head start sitting
right where they'd add the entry by hand.
"""

from collections.abc import Callable
from pathlib import Path

from pydantic import BaseModel

from extraction import Extraction
from redaction.elocution import default_systems
from redaction.elocution.base import System
from redaction.elocution.bibliography import BibliographyEntry, parse_bibliography, sniff_style
from redaction.elocution.canon import add_tier2
from redaction.elocution.citation_pairing import SiglumPairing, collisions, pair_sigla
from redaction.providers import Provider

_DRAFT_SYSTEM = """\
You are preparing a scholarly monograph's footnotes for text-to-speech \
narration. Each line below has the form "AUTHOR cites SIGLUM (Nx)": AUTHOR \
is a classical author, already confirmed, never yours to question; SIGLUM \
is an abbreviation this document's own footnotes use for one of that \
author's works (e.g. "Josephus cites AJ"). For each line you are confident \
about, return its SIGLUM copied character-for-character -- never AUTHOR, \
never "AUTHOR cites SIGLUM", never any punctuation around it -- paired with \
that work's standard English title. Skip any line you are not confident \
about rather than guessing; never invent a title.\
"""


class DraftSiglum(BaseModel):
    siglum: str
    spoken: str


class DraftSigla(BaseModel):
    entries: list[DraftSiglum]


def _bibliography(extraction: Extraction) -> list[BibliographyEntry]:
    raw_entries = [entry for section in extraction.sections for entry in section.bibliography]
    if not raw_entries:
        return []
    style = sniff_style(raw_entries)
    return parse_bibliography(raw_entries, style)


def _pairings(extraction: Extraction) -> list[SiglumPairing]:
    bibliography = _bibliography(extraction)
    return pair_sigla(bibliography, extraction.footnotes) if bibliography else []


def _known_sigla(elocution_dir: Path | None, directory: Path | None) -> set[str]:
    known: set[str] = set()
    for system in default_systems(elocution_dir=elocution_dir, directory=directory):
        if isinstance(system, System):
            known.update(system.sigla)
    return known


def _hints(bibliography: list[BibliographyEntry], author: str) -> list[str]:
    """This document's own bibliography entries for ``author``, verbatim."""
    return [entry.text for entry in bibliography if author in entry.authors]


def _ambiguous_stubs(
    pairings: list[SiglumPairing],
    bibliography: list[BibliographyEntry],
    ambiguous: dict[str, set[str]],
) -> dict[str, dict]:
    stubs = {}
    for siglum, authors in ambiguous.items():
        stubs[siglum] = {
            "note": 'ambiguous in this document — add "spoken" once you know which',
            "candidates": {
                author: next(
                    (p.count for p in pairings if p.author == author and p.siglum == siglum), 0
                )
                for author in sorted(authors)
            },
            "bibliography": {author: _hints(bibliography, author) for author in sorted(authors)},
        }
    return stubs


def candidates(
    extraction: Extraction, elocution_dir: Path | None, directory: Path | None
) -> list[SiglumPairing]:
    """Author-siglum pairings worth drafting: unresolved and unambiguous."""
    pairings = _pairings(extraction)
    known = _known_sigla(elocution_dir, directory)
    ambiguous = collisions(pairings)
    return [
        pairing
        for pairing in pairings
        if pairing.siglum is not None
        and pairing.siglum not in known
        and pairing.siglum not in ambiguous
    ]


def draft(
    extraction: Extraction,
    provider: Provider,
    elocution_dir: Path | None,
    directory: Path,
    log: Callable[[str], None] = lambda message: None,
) -> int:
    """Sweep for classical siglum candidates; merge resolutions into tier 2.

    A resolved entry already in tier 2 (hand-written or previously
    drafted) is never overwritten. Whatever stays unresolved after this
    run — ambiguous, or the model wasn't confident — is written as a stub
    instead of only logged (see this module's and ``canon.py``'s
    docstrings); a stub never overwrites another stub, so its bibliography
    hint stays stable rather than churning every run. Returns the number
    of newly resolved entries.
    """
    bibliography = _bibliography(extraction)
    pairings = pair_sigla(bibliography, extraction.footnotes) if bibliography else []
    ambiguous = collisions(pairings)
    stubs = _ambiguous_stubs(pairings, bibliography, ambiguous)
    known = _known_sigla(elocution_dir, directory)
    found = [
        pairing
        for pairing in pairings
        if pairing.siglum is not None
        and pairing.siglum not in known
        and pairing.siglum not in ambiguous
    ]
    path = directory / "classical.toml"
    resolved = 0
    if not found:
        log("classical draft: nothing new to ask the model")
    else:
        request = "\n".join(
            f"{pairing.author} cites {pairing.siglum} ({pairing.count}x)" for pairing in found
        )
        answer = provider.ask(_DRAFT_SYSTEM, request, DraftSigla)
        if answer is None:
            log("classical draft: model returned nothing usable")
        else:
            counts = {pairing.siglum: pairing.count for pairing in found}
            proposed = {
                item.siglum: {"spoken": item.spoken, "count": counts[item.siglum]}
                for item in answer.entries
                if item.siglum in counts
            }
            resolved = len(add_tier2(directory, "classical", proposed))
            for pairing in found:
                if pairing.siglum not in proposed:
                    stubs[pairing.siglum] = {
                        "note": "the model wasn't confident about this one",
                        "author": pairing.author,
                        "count": pairing.count,
                        "bibliography": _hints(bibliography, pairing.author),
                    }
    added_stubs = add_tier2(directory, "classical", stubs) if stubs else []
    if added_stubs:
        log(f"classical draft: {len(added_stubs)} siglum(s) left as stubs in {path} for a human")
    log(f"classical draft: {resolved} new entr{'y' if resolved == 1 else 'ies'} in {path}")
    return resolved
