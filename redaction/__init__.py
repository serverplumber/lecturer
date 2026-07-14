"""Rework the extracted text, layer by layer, into a script for the TTS to perform."""

from extraction import Extraction
from redaction.base import Manner, Redactor, Script, ScriptSection, Utterance
from redaction.mend import SeamMender
from redaction.weave import FootnoteWeaver

__all__ = [
    "Manner",
    "Redactor",
    "Script",
    "ScriptSection",
    "Utterance",
    "redact",
]

_LAYERS: list[Redactor] = [
    SeamMender(),
    FootnoteWeaver(),
]


def redact(extraction: Extraction) -> Script:
    """Apply every redactional layer, in order, to the extracted text."""
    script = Script.from_extraction(extraction)
    for layer in _LAYERS:
        script = layer.redact(script)
    return script
