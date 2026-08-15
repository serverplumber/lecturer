"""Rework the extracted text, layer by layer, into a script for the TTS to perform."""

from pathlib import Path

from extraction import Extraction
from redaction.base import Manner, Redactor, Script, ScriptSection, Utterance
from redaction.cantillation import Cantillator
from redaction.elocution import (
    BARE_AUTHORS,
    Elocutor,
    NearMiss,
    System,
    bare_author_system,
    default_systems,
)
from redaction.elocution.bibliography import parse_bibliography, sniff_style
from redaction.elocution.citation_pairing import pair_sigla
from redaction.estimate import check_budget, estimate_gloss_cost, price_tokens, render_estimate
from redaction.gloss import Glossator, RevertedParagraph, ensure_synopsis
from redaction.interpret import TongueInterpreter
from redaction.mend import SeamMender
from redaction.providers import DEFAULT_MODELS, PROVIDERS, TAGGING_MODELS, ProviderError
from redaction.tongues import LanguageTagger
from redaction.weave import FootnoteWeaver, NoteDropper

__all__ = [
    "DEFAULT_MODELS",
    "PROVIDERS",
    "TAGGING_MODELS",
    "Cantillator",
    "Elocutor",
    "FootnoteWeaver",
    "Glossator",
    "Manner",
    "NearMiss",
    "NoteDropper",
    "ProviderError",
    "Redactor",
    "RevertedParagraph",
    "Script",
    "ScriptSection",
    "System",
    "TongueInterpreter",
    "Utterance",
    "check_budget",
    "default_systems",
    "ensure_synopsis",
    "estimate_gloss_cost",
    "price_tokens",
    "redact",
    "render_estimate",
]


def redact(
    extraction: Extraction,
    weaver: Redactor | None = None,
    interpreter: Redactor | None = None,
    systems: tuple[System, ...] | None = None,
    directory: Path | None = None,
    elocution_dir: Path | None = None,
) -> tuple[Script, list[NearMiss]]:
    """Apply every redactional layer, in order, to the extracted text.

    ``weaver`` replaces the default ``NoteDropper`` — pass a ``Glossator``
    to weave footnotes in with the LLM's judgement, or a ``FootnoteWeaver``
    to weave them in verbatim for inspection. ``systems`` replaces
    :func:`default_systems` entirely for the citation ``Elocutor``, run
    right after weaving so a woven-in note's own citations get spoken too.
    Left as ``None``, the default is augmented per document with
    :func:`_bare_author_systems` — bare-cited authors *beyond*
    ``default_systems()``'s own closed ``bare_authors_system()`` that this
    specific document's bibliography and footnotes independently confirm
    — rather than left as the fully static ``default_systems()``; passing
    ``systems`` explicitly is still the only way to bypass both.
    ``directory``/``elocution_dir`` thread through to :func:`default_systems`
    for classical's two external tiers (``canon.py``) — this document's own
    ``directory / "classical_sigla.toml"`` and the shared canon at
    ``elocution_dir / "classical_sigla.toml"``; left ``None``, classical
    falls back to its bare hardcoded seed.
    ``interpreter`` (a ``TongueInterpreter``) tags Latin-alphabet language
    switches after the deterministic tagger has handled the writing
    systems. Alongside the script, returns the citation ``Elocutor``'s own
    near-misses — citation-shaped spans it found but couldn't convert —
    for the caller to write out for a human to check by eye.
    """
    if systems is None:
        systems = (
            *default_systems(elocution_dir=elocution_dir, directory=directory),
            *_bare_author_systems(extraction),
        )
    elocutor = Elocutor(systems)
    layers: list[Redactor] = [
        SeamMender(),
        weaver or NoteDropper(),
        elocutor,
        LanguageTagger(),
        *([interpreter] if interpreter is not None else []),
        Cantillator(),
    ]
    script = Script.from_extraction(extraction)
    for layer in layers:
        script = layer.redact(script)
    return script, elocutor.near_misses


def _bare_author_systems(extraction: Extraction) -> tuple[System, ...]:
    """Bare-cited authors beyond ``bare_authors.py``'s own closed list.

    Which classical authors are conventionally cited bare (one well-known
    work, no siglum needed — "Cassius Dio, 57.25.8") turned out to be a
    fact about the *author*, not about any one book's own bibliography:
    Livy is cited exactly that way in ``temple_gates`` too, but has no
    separate bibliography entry there at all, so a purely document-derived
    check can't confirm him — that's why the well-evidenced cases live in
    ``bare_authors.py``'s closed ``BARE_AUTHORS`` instead, applied
    universally via ``default_systems()``. This function is the
    supplementary layer for whatever a *specific* document's own
    bibliography independently confirms beyond that closed list — reads
    ``sniff_style`` → ``parse_bibliography`` → ``pair_sigla`` off the
    extraction's own bibliography and footnotes; every step already
    abstains rather than guesses when its own evidence is thin (an
    unrecognised bibliography style, or no bibliography section at all),
    so a document with nothing new to confirm just contributes no extra
    system, silently, rather than needing its own opt-out.
    """
    raw_entries = [entry for section in extraction.sections for entry in section.bibliography]
    if not raw_entries:
        return ()
    style = sniff_style(raw_entries)
    entries = parse_bibliography(raw_entries, style)
    pairings = pair_sigla(entries, extraction.footnotes)
    bare_authors = [
        pairing.author
        for pairing in pairings
        if pairing.siglum is None and pairing.author not in BARE_AUTHORS
    ]
    return (bare_author_system(bare_authors),) if bare_authors else ()
