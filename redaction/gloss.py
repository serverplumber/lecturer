"""Weave footnotes into the text with a lecturer's judgement — the LLM layer.

The medieval glossators worked marginal glosses into the running commentary;
this layer does the same to footnotes, with the judgement the deterministic
weaver lacks: substantive notes are respoken as asides in the author's
lecturing voice, bare citations are dropped rather than read out, and mixed
notes keep their substance while shedding the bibliographic apparatus. The
author's own prose is never touched — the model only removes the anchors and
decides what each note becomes, and a faithfulness check enforces it: every
body piece must be a verbatim stretch of the original paragraph, so a model
that paraphrases (weaker local models especially) costs a fallback to the
deterministic weave, never corrupted prose.

Each annotated paragraph is one call through a provider adapter, prefixed
by a cache-stable context: a short stored synopsis of the whole book (the
voice, the argument — see :func:`ensure_synopsis`) plus the full chapter
the paragraph belongs to, so the model can judge redundancy and reference
against the text the notes actually hang off. Results are cached
write-through in the working directory, keyed by provider and paragraph
inputs only — context refinements never invalidate finished work.
"""

import hashlib
import json
import re
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from pathlib import Path

from pydantic import BaseModel

from extraction import Footnote
from redaction.base import ANCHOR, Manner, Script, ScriptSection, Utterance
from redaction.providers import Provider, WovenParagraph
from redaction.weave import weave_utterance

_SYSTEM = """\
You are adapting a scholarly monograph into an audiobook that sounds like the \
author lecturing from their own book. You are given one paragraph of the running \
text, in which footnote anchors appear as [^ref] markers, together with the \
footnotes they point to.

Recast the paragraph as a sequence of spoken stretches, each labelled "body" or \
"digression":

- body: the author's prose, verbatim — change nothing except removing the [^ref] \
markers. Never paraphrase, trim, or reorder body text.
- digression: a footnote woven in as a spoken aside, placed after the sentence \
that carries its anchor. Respeak the note in the author's lecturing voice so it \
works as something said, not read: first person where natural, no "see" or "cf.", \
no page numbers.

Judge each note:
- Substantive notes (arguments, qualifications, evidence, anecdotes) become \
digressions.
- Bare citations (author, title, journal, pages) are dropped silently — a lecturer \
does not read out a bibliography. Name the source aloud only when it serves the \
listener, e.g. "the story is in Livy".
- Mixed notes keep their substance and shed the bibliographic apparatus.

Keep quotations, including Greek, Hebrew, and other languages, exactly as written. \
Do not invent anything found in neither the paragraph nor the notes.\
"""

# Characters ignored when checking body pieces against the source: invisible
# typesetting artefacts a model may reasonably drop.
_INVISIBLES = re.compile(r"[​‌‍⁠­]")

_SYNOPSIS_SYSTEM = """\
You are preparing to adapt a scholarly monograph into an audiobook read in \
the author's own lecturing voice. Write a synopsis of about 300 tokens for \
the adaptation assistants who will each see only one chapter at a time: the \
book's central argument and its arc, the author's voice and register, and \
the recurring sources, terms, and figures. No praise, no padding — only \
what helps someone weave the author's footnotes into speech.\
"""


class Synopsis(BaseModel):
    synopsis: str


def ensure_synopsis(extraction, provider: Provider, path: Path, log=lambda m: None) -> str | None:
    """The book synopsis, generated once by a capable model, then yours.

    Stored as ``synopsis.txt`` in the work dir and never regenerated —
    edit it freely; delete it to re-draft. Synopsis quality gates every
    gloss judgement downstream, so this uses the glossator's model, not
    the cheap tier.
    """
    if path.exists():
        return path.read_text().strip() or None
    text = "\n\n".join(section.text for section in extraction.sections)
    answer = provider.ask(_SYNOPSIS_SYSTEM, text[:600_000], Synopsis)
    if answer is None:
        return None
    path.write_text(answer.synopsis.strip() + "\n")
    log(f"synopsis drafted into {path} — edit it freely; it is never regenerated")
    return answer.synopsis.strip()


@dataclass
class PendingParagraph:
    """One paragraph a real ``redact --llm`` run would still call the model for.

    Built by :meth:`Glossator.pending_paragraphs` for
    ``redaction/estimate.py``'s cost estimate — never sent anywhere.
    """

    section_title: str
    section_index: int  # groups paragraphs by chapter even if two sections share a title
    request: str
    context: str | None
    key: str


class Glossator:
    """LLM counterpart to the deterministic FootnoteWeaver."""

    def __init__(
        self,
        provider: Provider,
        cache_path: Path | None = None,
        synopsis: str | None = None,
        log: Callable[[str], None] = lambda message: None,
    ) -> None:
        self.provider = provider
        self._synopsis = synopsis
        self._cache_path = cache_path
        self._cache: dict[str, list[dict]] = {}
        if cache_path is not None and cache_path.exists():
            self._cache = json.loads(cache_path.read_text())
        self._log = log
        # Billed calls this instance has actually made (cache misses that
        # reached _ask, truncated ones included) — the honest denominator for
        # a per-paragraph output average, since a resumed run's cache hits
        # cost nothing more. Token counters baseline against the provider's
        # own running totals at construction time, so usage the provider
        # accrued before this Glossator existed (e.g. ensure_synopsis, called
        # just before construction in lecturer.py) is never attributed here.
        self.calls = 0
        self._baseline_input = provider.input_tokens
        self._baseline_output = provider.output_tokens
        self._baseline_truncated = getattr(provider, "truncated", 0)

    @property
    def gloss_input_tokens(self) -> int:
        return self.provider.input_tokens - self._baseline_input

    @property
    def gloss_output_tokens(self) -> int:
        return self.provider.output_tokens - self._baseline_output

    @property
    def gloss_truncated(self) -> int:
        return getattr(self.provider, "truncated", 0) - self._baseline_truncated

    @property
    def cache_size(self) -> int:
        return len(self._cache)

    def redact(self, script: Script) -> Script:
        return Script(sections=[self._gloss_section(section) for section in script.sections])

    def _gloss_section(self, section: ScriptSection) -> ScriptSection:
        notes = {note.ref: note for note in section.footnotes}
        annotated = sum(bool(ANCHOR.search(u.text)) for u in section.utterances)
        if annotated:
            self._log(f"glossing '{section.title}': {annotated} annotated paragraphs")
        context = self._context(section) if annotated else None
        woven: set[str] = set()
        utterances: list[Utterance] = []
        for utterance in section.utterances:
            if utterance.manner is Manner.BODY:
                utterances.extend(
                    self._gloss_utterance(section.title, utterance, notes, woven, context)
                )
            else:
                utterances.append(utterance)
        leftovers = [note for ref, note in notes.items() if ref not in woven]
        return ScriptSection(title=section.title, utterances=utterances, footnotes=leftovers)

    def _context(self, section: ScriptSection) -> str:
        """The cache-stable prefix: book synopsis plus the whole chapter."""
        chapter = "\n\n".join(u.text for u in section.utterances)
        synopsis = f"Book synopsis:\n{self._synopsis}\n\n" if self._synopsis else ""
        return f"{synopsis}The full chapter this paragraph belongs to:\n{chapter}"

    def _gloss_utterance(
        self,
        section_title: str,
        utterance: Utterance,
        notes: dict[str, Footnote],
        woven: set[str],
        context: str | None,
    ) -> list[Utterance]:
        refs = [match.group(1) for match in ANCHOR.finditer(utterance.text)]
        if not refs:
            return [utterance]
        present = {ref: notes[ref] for ref in refs if ref in notes}

        key = self._key(utterance.text, present)
        pieces = self._cache.get(key)
        if pieces is None:
            self.calls += 1
            pieces = self._ask(section_title, utterance.text, present, context)
            if pieces is None:
                return weave_utterance(utterance, notes, woven)
            self._cache[key] = pieces
            self._save_cache()
        # Dropping a bare citation is the model doing its job, so every note
        # it saw counts as handled; only anchorless notes stay leftover.
        woven.update(present)
        return [Utterance(text=piece["text"], manner=Manner(piece["manner"])) for piece in pieces]

    def _ask(
        self,
        section_title: str,
        paragraph: str,
        notes: dict[str, Footnote],
        context: str | None = None,
    ) -> list[dict] | None:
        request = _request_text(section_title, paragraph, notes)
        woven = self.provider.ask(_SYSTEM, request, WovenParagraph, context=context)
        if woven is None or not _faithful(woven, paragraph):
            return None
        return [piece.model_dump() for piece in woven.pieces if piece.text.strip()]

    def _annotated(
        self, script: Script
    ) -> Iterator[tuple[str, int, str, dict[str, Footnote], str | None, str]]:
        """Every annotated paragraph in ``script``, cached or not.

        Yields ``(section_title, section_index, paragraph_text, notes,
        context, key)`` — the one walk shared by ``pending_paragraphs`` and
        ``stale_cache_entries`` so the two can't drift apart. ``script`` is
        expected to have already been through ``SeamMender``, matching where
        the glossator sits in ``redact()``'s layer order.
        """
        for section_index, section in enumerate(script.sections):
            notes = {note.ref: note for note in section.footnotes}
            annotated = any(
                utterance.manner is Manner.BODY and ANCHOR.search(utterance.text)
                for utterance in section.utterances
            )
            context = self._context(section) if annotated else None
            for utterance in section.utterances:
                if utterance.manner is not Manner.BODY:
                    continue
                refs = [match.group(1) for match in ANCHOR.finditer(utterance.text)]
                if not refs:
                    continue
                present = {ref: notes[ref] for ref in refs if ref in notes}
                key = self._key(utterance.text, present)
                yield section.title, section_index, utterance.text, present, context, key

    def pending_paragraphs(self, script: Script) -> list[PendingParagraph]:
        """Paragraphs a real ``redact --llm`` run would still call the model for.

        Never calls the model — used by ``redaction/estimate.py``.
        """
        return [
            PendingParagraph(
                section_title=title,
                section_index=index,
                request=_request_text(title, text, notes),
                context=context,
                key=key,
            )
            for title, index, text, notes, context, key in self._annotated(script)
            if key not in self._cache
        ]

    def stale_cache_entries(self, script: Script) -> int:
        """Cached glosses in this work dir that match no paragraph in ``script``.

        ``_key`` hashes ``provider.label`` (which encodes the model) into
        every cache key, so switching the configured model — including via
        ``DEFAULT_MODELS``' own default changing between runs — silently
        orphans every entry a prior run under the old model produced: not a
        cache lookup failure, a real edge case, since those paragraphs will
        be re-sent and re-billed rather than reused. Editing the source text
        or this file's own weaving pipeline would also orphan entries, so a
        nonzero count here isn't proof of a model change specifically — but
        it's the single most likely cause, and cheap to check. See
        CLAUDE.md's Glossator section for how this was found (a real ~145
        entries orphaned in a real work dir's gloss_cache.json switching
        this project's own default model mid-book) and confirmed.
        """
        matched = {key for *_, key in self._annotated(script) if key in self._cache}
        return len(self._cache) - len(matched)

    def _key(self, paragraph: str, notes: dict[str, Footnote]) -> str:
        payload = json.dumps(
            [self.provider.label, paragraph, {ref: note.text for ref, note in notes.items()}],
            sort_keys=True,
        )
        return hashlib.sha256(payload.encode()).hexdigest()

    def _save_cache(self) -> None:
        if self._cache_path is not None:
            partial = self._cache_path.with_suffix(self._cache_path.suffix + ".part")
            partial.write_text(json.dumps(self._cache, ensure_ascii=False, indent=1))
            partial.rename(self._cache_path)


def _request_text(section_title: str, paragraph: str, notes: dict[str, Footnote]) -> str:
    """The per-paragraph request text — shared by ``_ask`` and ``pending_paragraphs``.

    Kept in one place so a cost estimate (which never calls the model) sends
    ``count_tokens`` exactly the text a real call would send.
    """
    notes_block = "\n".join(f"[^{ref}]: {note.text}" for ref, note in notes.items())
    return (
        f"Section: {section_title}\n\nParagraph:\n{paragraph}\n\nFootnotes:\n{notes_block}"
        "\n\nRemember: body pieces are verbatim, but digressions are never copied "
        "from the note — respeak the note's substance aloud in the author's voice "
        "and drop the bibliographic apparatus. A purely bibliographic note "
        "produces no digression at all."
    )


def _faithful(woven: WovenParagraph, paragraph: str) -> bool:
    """True if the body pieces reproduce the whole paragraph, in order.

    Joined back together, the body pieces must equal the anchor-stripped
    paragraph — comparison ignores whitespace runs and invisible typesetting
    characters, nothing else. A model that paraphrased, reordered, or
    "improved" the prose fails, and so does one that quietly swallowed a
    sentence (weaker local models drop whole stretches): the author's text
    must survive verbatim and in full, or the paragraph falls back to the
    deterministic weave.
    """
    source = _collapse(ANCHOR.sub("", paragraph))
    bodies = [_collapse(piece.text) for piece in woven.pieces if piece.manner == "body"]
    return " ".join(body for body in bodies if body) == source


def _collapse(text: str) -> str:
    return " ".join(_INVISIBLES.sub("", text).split())
