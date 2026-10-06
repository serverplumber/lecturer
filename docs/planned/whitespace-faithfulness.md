# Spec: whitespace-blind faithfulness check

Status: implemented, as specified. No dependencies on other open specs.
Written for handoff to a fresh session — self-contained.

## Purpose

`Glossator`'s faithfulness guard (`redaction/gloss.py`'s `_faithful`)
requires the model's body pieces, joined back together, to equal the
anchor-stripped source paragraph. It already ignores whitespace _runs_ and
invisible typesetting characters, but still treats the presence or absence
of a single space as significant. Every reject whose cause has been
identified so far is that one-space difference, at a footnote anchor,
where the model's spacing was the correct one and the source's wasn't.

The output is an audiobook. Whitespace reaches the listener only through
word boundaries, and in every case seen the model _repaired_ a boundary the
source had broken. Comparing with whitespace removed entirely keeps
everything the guard exists to catch — paraphrase, reordering, dropped
sentences — since the letters must still match exactly and in order.

## Evidence

Three variants of the same gap, all at anchor positions:

1. **Space inside the anchor markup**, lost by extraction.
   `Bogomils<sup>37 </sup>into` extracted as `Bogomils[^n37]into`, so
   `_faithful`'s source read `Bogomilsinto` and rejected the model's
   `Bogomils into`. 19 of `eros_magic`'s 77 rejects. Fixed at extraction
   (`noteref_marker`, `ebffb45`), so no longer reaches the guard.
2. **Space missing from the book itself.** `ideas_and_ideals`' EPUB has
   `Johnson<sup>…20…</sup>is well known` and
   `Strasbourg in 1619.<sup>…27…</sup>Andreae’s`, no space anywhere in the
   markup. Extraction is right to reproduce that. The model wrote
   `Johnson is` and `1619. Andreae’s`, and the one difference between
   source and response in each case was that space — read off the
   responses `gloss_rejects.json` kept (`de5f317`). Both rejected again
   under `claude-opus-5-5`; these are the 2 still reverted.
3. **The space `_faithful` itself inserts.** Body pieces are joined with
   `" "`, so a model that splits the body at `Sinhachī[^62]—in` to place a
   digression produces `Sinhachī —in` against a source of `Sinhachī—in`.
   3 of `eros_magic`'s rejects had this shape. They passed under
   `claude-opus-5-5`, presumably by not splitting there, but the check
   would still reject one that did.

`eros_magic`'s other 55 rejects under `claude-opus-5` had no visible cause
and all passed on retry under `claude-opus-5-5`; their responses were never
kept, so whether they were whitespace too is unknown.

## Change

In `_faithful`, compare with all whitespace removed rather than collapsed:

```python
def _faithful(woven: WovenParagraph, paragraph: str) -> bool:
    source = _letters(ANCHOR.sub("", paragraph))
    bodies = "".join(_letters(p.text) for p in woven.pieces if p.manner == "body")
    return bodies == source


def _letters(text: str) -> str:
    return "".join(_INVISIBLES.sub("", text).split())
```

`_collapse` has no other caller and goes away. Rewrite `_faithful`'s
docstring to say whitespace is ignored entirely and why (word boundaries
are the only part a listener hears, and the model's have been more correct
than the source's). The spoken text is unchanged in kind: it was always the
model's body pieces, never the source — only the check's tolerance moves.

Cache keys hash the paragraph inputs, not the check, so nothing cached is
invalidated.

## Replaying kept rejects

A reject the new check would accept already has its response on disk, in
`gloss_rejects.json`. Re-billing it is waste. Add a replay step, run at the
start of `Glossator.redact` (or as part of `_lookup` on a cache miss):
for each kept entry, re-run `_faithful` on each attempt against the stored
paragraph; the first that passes is written to `gloss_cache.json` under the
entry's key and the entry is dropped from the rejects file. Same
write-through as the cache. `pending_paragraphs` must see the replay too,
or `estimate-gloss` will price paragraphs that won't be billed — doing the
replay in `_lookup` gets that for free, since `_annotated` already routes
through it.

Verify on `ideas_and_ideals`: after the change, `estimate-gloss` should
report 0 remaining paragraphs, and `redact --llm` should bill nothing while
`review.md` reports nothing reverted.

## Out of scope: the `book` variant

The `book` and `verbatim` variants never pass through the model, so
`1619.Andreae` is still spoken run together there (`NoteDropper` strips the
anchor, nothing adds a space). That needs a separate extraction-side rule:
when an anchor sits directly between non-whitespace and a following
_letter_, emit a space after the marker. Dashes and brackets aren't
letters, so `Sinhachī[^62]—in` and the other correctly-glued cases stay
untouched. Worth its own spec and its own corpus-wide before/after diff,
the same way `noteref_marker` was verified across all 9 EPUBs.

## Non-goals

- Tolerating any non-whitespace difference — punctuation, case, quotes,
  dashes. None has been observed, and each would let real edits through.
- Making the comparison fuzzy (edit distance, similarity ratio). The guard
  stays exact over letters; only whitespace stops counting.

## Open questions for whoever implements this

- Should a replayed reject be logged, so `review.md` can say how many
  paragraphs were recovered without a call? Settled: `redact` logs the
  count; `review.md` is unchanged, since a recovered paragraph has nothing
  left to review.
- A model could in principle split or merge real words (`in to`/`into`).
  The new check accepts that. No case has been seen; if one turns up,
  `gloss_rejects.json` won't catch it (it now passes), so the only place
  it would surface is listening.
