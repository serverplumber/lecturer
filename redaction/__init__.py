"""Rework the extracted text, layer by layer, into a script for the TTS to perform."""

from extraction import Extraction
from redaction.base import Manner, Redactor, Script, ScriptSection, Utterance
from redaction.gloss import Glossator
from redaction.mend import SeamMender
from redaction.providers import DEFAULT_MODELS, PROVIDERS, GlossError
from redaction.tongues import LanguageTagger
from redaction.weave import FootnoteWeaver

__all__ = [
    "DEFAULT_MODELS",
    "PROVIDERS",
    "GlossError",
    "Glossator",
    "Manner",
    "Redactor",
    "Script",
    "ScriptSection",
    "Utterance",
    "redact",
]


def redact(extraction: Extraction, weaver: Redactor | None = None) -> Script:
    """Apply every redactional layer, in order, to the extracted text.

    ``weaver`` replaces the deterministic footnote weaver — pass a
    ``Glossator`` to weave with the LLM's judgement instead.
    """
    layers: list[Redactor] = [SeamMender(), weaver or FootnoteWeaver(), LanguageTagger()]
    script = Script.from_extraction(extraction)
    for layer in layers:
        script = layer.redact(script)
    return script
