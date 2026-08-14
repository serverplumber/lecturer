# Spec: append-only JSONL for the gloss cache

Status: not started. Independent of the other two `docs/planned/` specs — no dependency
either way. Written for handoff to a fresh session — self-contained.

## Purpose

Replace `gloss_cache.json`'s full-file-rewrite-per-paragraph with an append-only JSONL
file, eliminating both the rewrite cost and the interrupt-corruption exposure in one move.

## Where this came from

Surfaced while fixing a real crash this session: `AnthropicProvider.ask` was throwing an
uncaught `pydantic_core.ValidationError` on a truncated response, killing a live `redact
--llm` run mid-book. Two fixes went in already (staged, not committed):

- `redaction/providers.py:112-113` — catch the `ValidationError`, fall back to the
  deterministic weave for that one paragraph instead of crashing the run.
- `redaction/gloss.py:199-202` (`_save_cache`) — write-then-rename instead of a direct
  `write_text`, matching the existing pattern in `recitation/kokoro.py`'s `_fetch`. This
  makes a single save atomic: an interrupt mid-write no longer corrupts the file.

The advisor's assessment at the time (worth restating here, since it's the reason this
spec exists): the temp+rename fix is correct and consistent with the codebase's own
convention, but it's containment, not the underlying fix. `_save_cache` rewrites the
**entire** cache dict from scratch after every single successful paragraph
(`_gloss_utterance` → `self._cache[key] = pieces; self._save_cache()`,
`redaction/gloss.py:127-128`). At 145 entries / 159KB (`eros_magic`'s real cache today)
that's cheap; across a full book it's hundreds of full-file rewrites of a growing file, and
the interrupt-exposure window scales with file size even with the atomic temp+rename in
place — a bigger file takes longer to serialize and write, so there's more wall-clock time
per save where an interrupt could land between the write starting and the rename landing
(harmless there specifically, since temp+rename already makes *that* window safe — but the
rewrite cost itself is real and grows with the book). An append-only log has neither
problem: appending one line is the atomic operation, and it's O(1) per save instead of
O(n) in the current cache size.

## Current shape (for reference)

```python
# __init__ — redaction/gloss.py:104-117
self._cache: dict[str, list[dict]] = {}
if cache_path is not None and cache_path.exists():
    self._cache = json.loads(cache_path.read_text())

# _save_cache — redaction/gloss.py:199-203 (post-fix)
def _save_cache(self) -> None:
    if self._cache_path is not None:
        partial = self._cache_path.with_suffix(self._cache_path.suffix + ".part")
        partial.write_text(json.dumps(self._cache, ensure_ascii=False, indent=1))
        partial.rename(self._cache_path)
```

Cache keys are a sha256 of `[provider.label, paragraph, notes]` (`_key`,
`redaction/gloss.py:191-197`) — the key already encodes everything needed to identify one
cached call; the value is the list of `WovenParagraph` pieces (dicts).

## Functional requirements

1. Change the on-disk format to one JSON object per line — `{"key": "<sha256>", "pieces":
   [...]}` (or key the line by putting the hash as a top-level object key, whichever reads
   more naturally; either is a one-line-per-entry format, the point is not needing to parse
   or rewrite the rest of the file to add one entry).
2. `_save_cache` (or its replacement) becomes an append: open in `"a"` mode, write one
   line, done. No more reading-and-rewriting the whole file per paragraph.
3. `__init__`'s load path reads the file line by line and rebuilds the in-memory `dict`
   exactly as today — the *in-memory* representation and the rest of `Glossator` (`_key`,
   `_ask`, `_gloss_utterance`) don't need to change at all. This is a storage-format change
   only, not a behavior change.
4. A truncated last line (the one genuine failure mode append-only doesn't fully rule out —
   a write interrupted mid-line, not mid-file) should be skippable rather than fatal: if the
   last line fails to parse, drop it and log rather than crashing the whole load. This is
   the one place this spec still needs *a* decision, just a much smaller one than "is the
   whole file corrupt."

## Migration — not optional, there's real money in the old format

Two work dirs already have populated `gloss_cache.json` files representing real, already-
paid-for Anthropic calls: `working_texts/eros_magic/gloss_cache.json` (145 entries, 159KB)
and `working_texts/temple_gates/gloss_cache.json` (81 entries, 152KB). Whatever ships here
must not orphan that work. Options, pick one at implementation time:

- **One-time convert on load**: if `gloss_cache.json` exists and the new `.jsonl` path
  doesn't, read the old format, write it out as JSONL, and proceed — cheap, automatic, no
  user action.
- **Dual-read, single-write**: load from either format if present, always write the new
  one going forward. Slightly more code, no conversion step to get wrong.

Either way, **do not delete the old `gloss_cache.json` until the new file is confirmed
readable** — this is exactly the kind of migration where a bug that drops the 145 entries
silently would cost real money to redo.

## Non-goals

- Not a fix for anything covered by the other two specs (cost estimation, budget gate) —
  fully independent.
- Not attempting to solve corruption recovery beyond the truncated-last-line case above —
  a fully corrupt file (rare, and now much rarer given both this format and the temp+rename
  fix) can still just fail loudly, same as today.

## Open questions for whoever implements this

- File extension / naming: `gloss_cache.jsonl` alongside (then replacing) `gloss_cache.json`.
- Exact line schema (key-as-field vs. key-as-object-key) — either works, pick for
  readability when a human opens the file, since that's part of this project's own
  "hand-editable artefact" convention elsewhere (e.g. the classical sigla TOML tiers).
- Whether the migration step belongs in `Glossator.__init__` itself or a separate one-time
  CLI verb — leaning toward automatic-in-`__init__` since it's cheap and safe, but flag for
  whoever builds it to confirm against the project's existing "draft-*/promote-*" verb
  conventions before deciding.
