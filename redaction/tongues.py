"""Tag switches into other tongues so the TTS can change delivery.

Deterministic where determinism is cheap: a change of writing system
identifies the language by Unicode codepoint alone, so quotations in
Greek, Hebrew, and their neighbours are found without any guessing. The
script-to-language mapping assumes a scholarly corpus — Greek script is
read as Ancient Greek, not Modern. Switches that stay within the Latin
alphabet (German and French titles in citations, Latin proper) are left
untagged: telling those apart takes judgement, which is the planned LLM
layer's business.

An utterance carries one language, so tagging splits utterances at script
boundaries; connectors (spaces, commas, dashes) between two runs of the
same script stay inside the foreign stretch, while surrounding brackets
and sentence punctuation stay with the host language.
"""

from redaction.base import Script, ScriptSection, Utterance

# Codepoint ranges per script, mapped to the language a scholarly monograph
# most plausibly quotes in that script.
_RANGES: tuple[tuple[int, int, str], ...] = (
    (0x0370, 0x03FF, "grc"),  # Greek and Coptic
    (0x1F00, 0x1FFF, "grc"),  # Greek Extended (polytonic)
    (0x0590, 0x05FF, "he"),  # Hebrew
    (0x0700, 0x074F, "syc"),  # Syriac
    (0x2C80, 0x2CFF, "cop"),  # Coptic
    (0x0600, 0x06FF, "ar"),  # Arabic
    (0x0400, 0x04FF, "ru"),  # Cyrillic
)

# Characters allowed to sit between two runs of the same script without
# breaking the stretch: word-level connectors, not sentence punctuation —
# spaces (plain, no-break, zero-width), commas, semicolons, ano teleia,
# dashes, apostrophes.
_CONNECTORS = set(" \u00a0\u200b,;\u00b7\u2014\u2013-'\u2019")


class LanguageTagger:
    def redact(self, script: Script) -> Script:
        return Script(
            sections=[
                ScriptSection(
                    title=section.title,
                    utterances=[
                        tagged
                        for utterance in section.utterances
                        for tagged in _tag_utterance(utterance)
                    ],
                    footnotes=section.footnotes,
                )
                for section in script.sections
            ]
        )


def _tag_utterance(utterance: Utterance) -> list[Utterance]:
    """Split one utterance into stretches of uniform language."""
    runs = _foreign_runs(utterance.text)
    if not runs:
        return [utterance]
    pieces: list[tuple[str, str]] = []
    consumed = 0
    for start, end, lang in runs:
        if host := utterance.text[consumed:start].strip():
            pieces.append((host, utterance.lang))
        pieces.append((utterance.text[start:end], lang))
        consumed = end
    if tail := utterance.text[consumed:].strip():
        pieces.append((tail, utterance.lang))
    return [
        Utterance(text=text, manner=utterance.manner, lang=lang)
        for text, lang in _absorb_crumbs(pieces)
    ]


def _absorb_crumbs(pieces: list[tuple[str, str]]) -> list[tuple[str, str]]:
    """Merge letterless pieces into a neighbour.

    Carving a quotation out of its sentence can leave the host language
    holding bare punctuation — an ellipsis before the quote, the full stop
    after it. Those aren't utterances; they trail the piece before them
    (or open the one after, at the very start).
    """
    merged: list[tuple[str, str]] = []
    opener = ""
    for text, lang in pieces:
        if not any(char.isalpha() for char in text):
            if merged:
                merged[-1] = (merged[-1][0] + text, merged[-1][1])
            else:
                opener += text
        else:
            merged.append((f"{opener} {text}" if opener else text, lang))
            opener = ""
    return merged


def _foreign_runs(text: str) -> list[tuple[int, int, str]]:
    """Maximal (start, end, lang) stretches of foreign script in ``text``."""
    runs: list[list] = []
    for position, char in enumerate(text):
        lang = _char_lang(char)
        if lang is None:
            continue
        if (
            runs
            and runs[-1][2] == lang
            and all(gap in _CONNECTORS for gap in text[runs[-1][1] : position])
        ):
            runs[-1][1] = position + 1
        else:
            runs.append([position, position + 1, lang])
    return [(start, end, lang) for start, end, lang in runs]


def _char_lang(char: str) -> str | None:
    codepoint = ord(char)
    for start, end, lang in _RANGES:
        if start <= codepoint <= end:
            return lang
    return None
