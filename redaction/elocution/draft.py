"""``draft-classical``: an LLM sweep that seeds classical.json's tier 2.

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
not a guess. Drafted entries land in tier 2 only (``canon.py``'s
``add_tier2``) — this document's ``classical.json`` — never tier 1: an LLM's
guess isn't evidence until a human runs ``promote-classical`` to say so,
the same posture ``add_tier2``/``promote`` already hold.
"""

from collections.abc import Callable
from pathlib import Path

from pydantic import BaseModel

from extraction import Extraction
from redaction.elocution import default_systems
from redaction.elocution.base import System
from redaction.elocution.bibliography import parse_bibliography, sniff_style
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


def _pairings(extraction: Extraction) -> list[SiglumPairing]:
    raw_entries = [entry for section in extraction.sections for entry in section.bibliography]
    if not raw_entries:
        return []
    style = sniff_style(raw_entries)
    entries = parse_bibliography(raw_entries, style)
    return pair_sigla(entries, extraction.footnotes)


def candidates(
    extraction: Extraction, elocution_dir: Path | None, directory: Path | None
) -> list[SiglumPairing]:
    """Author-siglum pairings worth drafting: unresolved and unambiguous."""
    pairings = _pairings(extraction)
    known: set[str] = set()
    for system in default_systems(elocution_dir=elocution_dir, directory=directory):
        if isinstance(system, System):
            known.update(system.sigla)
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
    """Sweep for classical siglum candidates; merge LLM drafts into tier 2.

    Existing tier-2 entries are never overwritten (``canon.py``'s
    ``add_tier2``). Returns the number of new entries.
    """
    ambiguous = collisions(_pairings(extraction))
    if ambiguous:
        spans = "; ".join(
            f"{siglum} ({'/'.join(sorted(authors))})" for siglum, authors in ambiguous.items()
        )
        log(f"classical draft: left {len(ambiguous)} ambiguous siglum(s) for a human — {spans}")
    found = candidates(extraction, elocution_dir, directory)
    if not found:
        log("classical draft: nothing to draft")
        return 0
    request = "\n".join(
        f"{pairing.author} cites {pairing.siglum} ({pairing.count}x)" for pairing in found
    )
    answer = provider.ask(_DRAFT_SYSTEM, request, DraftSigla)
    if answer is None:
        log("classical draft: model returned nothing usable")
        return 0
    counts = {pairing.siglum: pairing.count for pairing in found}
    proposed = {
        item.siglum: {"spoken": item.spoken, "count": counts[item.siglum]}
        for item in answer.entries
        if item.siglum in counts
    }
    added = add_tier2(directory, "classical", proposed)
    log(
        f"classical draft: {len(added)} new entr{'y' if len(added) == 1 else 'ies'} in "
        f"{directory / 'classical.json'}"
    )
    return len(added)
