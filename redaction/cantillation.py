"""Mark the breathing for the reciter — cantillation for the lecture.

A TTS model breathes where punctuation tells it to. Handed one of this
corpus's forty-word comma-free sentences, Kokoro improvises a breath at a
syntactically plausible but semantically wrong spot ("the actors — in
question"), and denying it one spot only moves the breath to the next bad
one. As the Masoretes pointed the consonantal text with cantillation marks
to fix its chanted phrasing, this layer points overlong stretches with
commas — never spoken, only breathed — at subordinate-clause boundaries,
so the model always has a sanctioned place to draw breath.

Only stretches longer than a breath already runs are touched; text that
carries its own punctuation is left exactly as the author wrote it.
"""

import re

from redaction.base import Script, ScriptSection, Utterance

# About as far as Kokoro reads aloud before improvising a breath.
_BREATH_CHARS = 110
# Never point a breath this close to the previous one.
_MIN_CLAUSE = 40

# Punctuation the model already breathes at (the en dash is intentional).
_BREATHS = re.compile(r"[,;:.!?…()—–]")  # noqa: RUF001
# Clause openers a lecturer may breathe before. "that" and "than" are
# excluded: the first is usually a determiner, the second a comparative
# the model phrases badly either way.
_MARKERS = re.compile(
    r"\s+(?=(?:where|which|who|whose|whom|when|while|because|although|though|"
    r"whereas|unless|since|until)\b)",
    re.IGNORECASE,
)
# A pied-piped relative ("with which", "of whom") is one unit: never breathe
# between the preposition and its pronoun.
_NO_BREATH_AFTER = frozenset(
    [
        "with",
        "in",
        "of",
        "to",
        "by",
        "for",
        "at",
        "from",
        "on",
        "upon",
        "under",
        "over",
        "against",
        "through",
        "during",
        "within",
        "without",
        "about",
        "between",
        "among",
        "across",
        "toward",
        "towards",
    ]
)


class Cantillator:
    """Point overlong clauses with breath commas."""

    def redact(self, script: Script) -> Script:
        return Script(
            sections=[
                ScriptSection(
                    title=section.title,
                    utterances=[
                        Utterance(text=_point(u.text), manner=u.manner, lang=u.lang)
                        if u.lang == "en"
                        else u
                        for u in section.utterances
                    ],
                    footnotes=section.footnotes,
                )
                for section in script.sections
            ]
        )


def _point(text: str) -> str:
    """Insert breath commas into stretches that outrun a breath."""
    candidates = []
    for match in _MARKERS.finditer(text):
        preceding = text[: match.start()].rsplit(None, 1)
        if preceding and preceding[-1].lower().strip("“”\"'()") in _NO_BREATH_AFTER:
            continue
        candidates.append(match.start())
    if not candidates:
        return text
    breaths = [match.start() for match in _BREATHS.finditer(text)] + [len(text)]
    insertions: list[int] = []
    last = 0
    for breath in sorted(set(breaths)):
        start = last
        while breath - start > _BREATH_CHARS:
            options = [c for c in candidates if start + _MIN_CLAUSE <= c < breath]
            within = [c for c in options if c <= start + _BREATH_CHARS]
            pick = max(within) if within else (min(options) if options else None)
            if pick is None:
                break
            insertions.append(pick)
            start = pick
        last = breath
    for position in sorted(insertions, reverse=True):
        text = text[:position] + "," + text[position:]
    return text
