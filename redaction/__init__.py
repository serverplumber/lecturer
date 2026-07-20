"""Rework the extracted text, layer by layer, into a script for the TTS to perform."""

from extraction import Extraction
from redaction.base import Manner, Redactor, Script, ScriptSection, Utterance
from redaction.cantillation import Cantillator
from redaction.elocution import Elocutor, System, default_systems
from redaction.gloss import Glossator, ensure_synopsis
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
    "NoteDropper",
    "ProviderError",
    "Redactor",
    "Script",
    "ScriptSection",
    "System",
    "TongueInterpreter",
    "Utterance",
    "default_systems",
    "ensure_synopsis",
    "redact",
]


def redact(
    extraction: Extraction,
    weaver: Redactor | None = None,
    interpreter: Redactor | None = None,
    systems: tuple[System, ...] | None = None,
) -> Script:
    """Apply every redactional layer, in order, to the extracted text.

    ``weaver`` replaces the default ``NoteDropper`` — pass a ``Glossator``
    to weave footnotes in with the LLM's judgement, or a ``FootnoteWeaver``
    to weave them in verbatim for inspection. ``systems`` replaces
    :func:`default_systems` for the citation ``Elocutor``, run right after
    weaving so a woven-in note's own citations get spoken too.
    ``interpreter`` (a ``TongueInterpreter``) tags Latin-alphabet language
    switches after the deterministic tagger has handled the writing
    systems.
    """
    layers: list[Redactor] = [
        SeamMender(),
        weaver or NoteDropper(),
        Elocutor(systems if systems is not None else default_systems()),
        LanguageTagger(),
        *([interpreter] if interpreter is not None else []),
        Cantillator(),
    ]
    script = Script.from_extraction(extraction)
    for layer in layers:
        script = layer.redact(script)
    return script
