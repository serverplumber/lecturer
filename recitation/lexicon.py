"""The pronunciation lexicon — how recurring names and terms are read aloud.

The redacted script keeps the author's exact words; ``lexicon.json`` in
the work dir maps recurring surface forms — names, terms of art — to
their pronunciation, applied at synthesis time. Three mechanisms, in
increasing order of control:

- ``as``: a respelling the phonemizer reads correctly ("Josephus" ->
  "Yosephus"), or Greek script to hand the word to the Reuchlinian route.
- ``lang``: pronounce the surface form through another language's rules
  (the per-word cousin of the transliteration -> Italian rule).
- ``ipa``: exact phonemes, for the stubborn cases.

Entries are drafted by a cheap LLM sweep (``--lexicon-draft``) and edited
by the listener's ear; matching is deterministic — whole words, longest
entry first, case-sensitive. Keys starting with ``_`` are ignored, and a
``count`` field inside an entry is bookkeeping from the draft, not
semantics.
"""

import hashlib
import json
import re
from collections.abc import Callable
from pathlib import Path

from pydantic import BaseModel

from redaction import Script
from redaction.providers import Provider

_MECHANISMS = frozenset(["as", "lang", "ipa"])


class Lexicon:
    def __init__(self, entries: dict[str, dict]) -> None:
        self.entries = {
            term: entry
            for term, entry in entries.items()
            if not term.startswith("_") and _MECHANISMS & entry.keys()
        }
        self.digest = hashlib.sha256(json.dumps(self.entries, sort_keys=True).encode()).hexdigest()
        terms = sorted(self.entries, key=len, reverse=True)
        self._pattern = (
            re.compile(r"\b(?:" + "|".join(re.escape(t) for t in terms) + r")\b") if terms else None
        )

    @classmethod
    def load(cls, path: Path) -> "Lexicon | None":
        if not path.exists():
            return None
        return cls(json.loads(path.read_text()))

    def split(self, text: str) -> list[tuple[str, dict | None]] | None:
        """Pieces of ``text`` with their lexicon entries; ``None`` if no hit."""
        if self._pattern is None or not self._pattern.search(text):
            return None
        pieces: list[tuple[str, dict | None]] = []
        consumed = 0
        for match in self._pattern.finditer(text):
            if before := text[consumed : match.start()].strip():
                pieces.append((before, None))
            pieces.append((match.group(0), self.entries[match.group(0)]))
            consumed = match.end()
        if after := text[consumed:].strip():
            pieces.append((after, None))
        return pieces

    def digest_for(self, text: str) -> str:
        """Digest of only the entries that occur in ``text``.

        Part of the audio signature: adding or editing an entry re-renders
        exactly the sections that mention it.
        """
        if self._pattern is None:
            return ""
        hits = sorted(set(self._pattern.findall(text)))
        if not hits:
            return ""
        payload = json.dumps([(term, self.entries[term]) for term in hits], sort_keys=True)
        return hashlib.sha256(payload.encode()).hexdigest()


_DRAFT_SYSTEM = """\
You are preparing a scholarly monograph for text-to-speech narration. You \
receive stretches of its running text. List the words a speech synthesiser \
will mispronounce by English letter-to-sound rules: proper names of people \
and places, transliterated ancient terms, and technical vocabulary. Ignore \
ordinary English.

For each term give either a phonetic respelling in plain English letters \
("Josephus" -> "Yosephus", "Ialdabaoth" -> "Yal-da-bah-oth") or, where the \
word should simply be read by another language's rules, a language code \
(la, it, fr, de, grc, he). Never give both. Return each term exactly as \
spelled in the text.\
"""


class DraftTerm(BaseModel):
    term: str
    respell: str | None = None
    lang: str | None = None


class DraftTerms(BaseModel):
    terms: list[DraftTerm]


def draft(
    script: Script,
    provider: Provider,
    path: Path,
    log: Callable[[str], None] = lambda message: None,
) -> int:
    """Sweep the script for pronunciation risks; merge drafts into the lexicon.

    Existing entries are never overwritten — the file is the listener's to
    edit. New entries land with an occurrence ``count``, most frequent
    first, so pruning starts at the top. Returns the number of new entries.
    """
    existing: dict[str, dict] = json.loads(path.read_text()) if path.exists() else {}
    text = "\n".join(u.text for s in script.sections for u in s.utterances if u.lang == "en")
    found: dict[str, dict] = {}
    for batch in _batches(text):
        answer = provider.ask(_DRAFT_SYSTEM, batch, DraftTerms)
        if answer is None:
            continue
        for term in answer.terms:
            if term.term in existing or term.term in found or term.term not in batch:
                continue
            if term.respell:
                found[term.term] = {"as": term.respell}
            elif term.lang:
                found[term.term] = {"lang": term.lang.lower()}
    for term, entry in found.items():
        entry["count"] = len(re.findall(rf"\b{re.escape(term)}\b", text))
    ranked = dict(sorted(found.items(), key=lambda kv: -kv[1]["count"]))
    merged = {**existing, **ranked}
    path.write_text(json.dumps(merged, ensure_ascii=False, indent=1))
    log(f"lexicon: {len(ranked)} new draft entries ({len(merged)} total) in {path}")
    return len(ranked)


def _batches(text: str, budget: int = 3500):
    lines = text.splitlines()
    batch: list[str] = []
    size = 0
    for line in lines:
        if batch and size + len(line) > budget:
            yield "\n".join(batch)
            batch, size = [], 0
        batch.append(line)
        size += len(line)
    if batch:
        yield "\n".join(batch)
