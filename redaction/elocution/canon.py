"""The two external layers an open-vocabulary system's sigla table is built from.

A closed system's table (biblical.py, stephanus.py, ...) is finished, verified
Python and stays that way — the near-miss review is the right tool for a gap
there, and fixing one means a normal commit. An open system's table (starting
with classical.py) is never finished, so it gets two more layers on top of its
own hardcoded seed, weakest to strongest:

- **Tier 1**, ``<elocution_dir>/<system>_sigla.toml`` — this machine's shared,
  hand-curated canon, valid for every document. Only ``promote`` ever writes
  it, and does so with ``tomlkit`` so a human's own comments and formatting
  survive a programmatic edit. Never touched by a draft sweep directly — an
  LLM's guess isn't evidence until a human decides to promote it.
- **Tier 2**, ``<work dir>/<system>_sigla.toml`` — this one document's own
  entries, hand-edited or drafted (``draft-classical``, on the ``lexicon.py``
  pattern: additive, never overwriting a resolved entry).

Both tiers are TOML, both for the same reason: an entry can carry a real
comment recording *why* — the same provenance the closed tables keep inline
("collides with biblical's Numbers; classical wins the tie"), and, in tier
2's case, a stub's own rationale for staying unresolved (see below). Tier 2
being written by tooling as well as by hand isn't a reason to prefer JSON
there — ``promote`` already proves ``tomlkit`` writes TOML programmatically
just fine, comments and all, so there was never a real reason to split
formats between the two tiers.

Precedence is seed < tier 1 < tier 2: a document's own file can override the
shared canon, which can override the hardcoded seed, each layer more specific
than the last. Keys starting with ``_`` are ignored, same convention as
``lexicon.py``, so a drafted file can carry its own bookkeeping without it
being read as a siglum.

Tier 2 can also hold **stubs**: a siglum ``draft`` (``redaction/elocution/
draft.py``) found but couldn't resolve — genuinely ambiguous in this
document, or one the model wasn't confident about — with no ``spoken`` key
at all, so ``_entries`` (and everything downstream of it) ignores it exactly
as if it weren't there. What it does carry is a real comment recording why,
and, where the document's own bibliography names the author, a
``bibliography`` hint — the same abstain-over-guess posture as the near-miss
review, applied to sigla resolution instead of citation matching: reported,
not dropped, so a human finds it sitting right where they'd add the entry by
hand, with a head start rather than a blank line. A resolved entry is a
short, flat inline table (fits one line: ``spoken``, maybe ``count``); a
stub is a real ``[siglum]`` table instead — TOML forbids a newline inside
``{...}`` (``tomllib`` rejects it outright), and a stub's own
``bibliography`` — a whole citation per author — never fits one reasonable
line regardless, so it gets its own ``[siglum.bibliography]`` sub-table, one
author's citation per line, rather than one line straining to hold all of
it.
"""

import tomllib
from pathlib import Path

import tomlkit


def tier1_path(elocution_dir: Path, system: str) -> Path:
    return elocution_dir / f"{system}_sigla.toml"


def tier2_path(directory: Path, system: str) -> Path:
    return directory / f"{system}_sigla.toml"


def _resolved(entry) -> bool:
    """A real answer, not a stub left for a human (see the module docstring)."""
    spoken = entry.get("spoken")
    return isinstance(spoken, str) and bool(spoken)


def _entries(data: dict) -> dict[str, str]:
    return {
        siglum: entry["spoken"]
        for siglum, entry in data.items()
        if not siglum.startswith("_") and _resolved(entry)
    }


def load_tier1(elocution_dir: Path | None, system: str) -> dict[str, str]:
    """This machine's shared canon for ``system``, siglum -> spoken form."""
    if elocution_dir is None:
        return {}
    path = tier1_path(elocution_dir, system)
    if not path.exists():
        return {}
    return _entries(tomllib.loads(path.read_text()))


def load_tier2(directory: Path | None, system: str) -> dict[str, str]:
    """This document's own entries for ``system``, siglum -> spoken form."""
    if directory is None:
        return {}
    path = tier2_path(directory, system)
    if not path.exists():
        return {}
    return _entries(tomllib.loads(path.read_text()))


def merged_sigla(
    seed: dict[str, str], elocution_dir: Path | None, directory: Path | None, system: str
) -> dict[str, str]:
    """``seed`` (hardcoded) overlaid by tier 1, overlaid by tier 2 — later wins."""
    return {
        **seed,
        **load_tier1(elocution_dir, system),
        **load_tier2(directory, system),
    }


def _resolved_entry(entry: dict) -> tomlkit.items.InlineTable:
    """A resolved entry's fields as a flat inline table — always short (``spoken``, ``count``)."""
    table = tomlkit.inline_table()
    for key, value in entry.items():
        if key != "note":
            table[key] = value
    return table


def _stub_entry(entry: dict) -> tomlkit.items.Table:
    """A stub's fields as a real ``[siglum]`` table, not one crammed inline line.

    ``candidates`` (a handful of short author: count pairs) stays inline —
    it fits one line fine. ``bibliography`` — a full citation per author —
    is left as a plain dict for ``tomlkit`` to auto-expand into its own
    ``[siglum.bibliography]`` sub-table, one author's citation per line,
    since no reasonable line width holds more than one of those at a time.
    """
    table = tomlkit.table()
    for key, value in entry.items():
        if key == "note" or key == "bibliography":
            continue
        if isinstance(value, dict):
            inline = tomlkit.inline_table()
            for k, v in value.items():
                inline[k] = v
            value = inline
        table[key] = value
    if "bibliography" in entry:
        table["bibliography"] = entry["bibliography"]
    return table


def add_tier2(directory: Path, system: str, entries: dict[str, dict]) -> list[str]:
    """Merge ``entries`` into tier 2 — additive, with one exception for stubs.

    A siglum already resolved (a real ``spoken`` value, hand-written or
    previously drafted) is never touched, mirroring ``lexicon.py``'s
    ``draft``: the file is the reader's to hand-edit. A siglum only
    present as a *stub* — left for a human by ``draft`` when it's
    ambiguous or the model wasn't confident, see this module's docstring —
    is the one thing allowed to change without a human editing it first:
    a later, more confident resolution can fill it in. Two stubs never
    replace each other, so a stub's own bibliography hints stay stable
    once written rather than churning on every draft run. An entry's own
    ``note`` (if any) is written as a real TOML comment immediately above
    its key, not a field. ``tomlkit`` keeps every flat (resolved) entry
    ahead of every ``[siglum]`` table (stub) regardless of insertion order
    — required, not cosmetic: TOML reads a bare ``key = value`` after a
    table header as belonging to that table, so a resolved entry appended
    after an existing stub would otherwise silently nest inside it.
    """
    path = tier2_path(directory, system)
    doc = tomlkit.parse(path.read_text()) if path.exists() else tomlkit.document()
    added = []
    for siglum, entry in entries.items():
        current = doc.get(siglum)
        if current is not None and (_resolved(current) or not _resolved(entry)):
            continue
        if note := entry.get("note"):
            doc.add(tomlkit.comment(note))
        doc[siglum] = _resolved_entry(entry) if _resolved(entry) else _stub_entry(entry)
        added.append(siglum)
    if added:
        directory.mkdir(parents=True, exist_ok=True)
        path.write_text(tomlkit.dumps(doc))
    return added


def promote(elocution_dir: Path, directory: Path, system: str) -> list[str]:
    """Copy this document's tier-2 entries for ``system`` into the shared tier-1 canon.

    Additive only, same posture as ``add_tier2``: a siglum tier 1 already has
    is left exactly as it was, comments and all — this never resolves a
    disagreement between a document's own file and the shared canon, only
    fills in what tier 1 doesn't have yet. Only ``spoken`` travels — a
    stub's ``note``/``candidates``/``bibliography`` are this document's own
    scratch context, not a fact about the siglum worth keeping once
    resolved. The one place tier 1 is ever written by code rather than by a
    human's editor, and even then only because a human ran this command to
    say so.
    """
    tier2_file = tier2_path(directory, system)
    if not tier2_file.exists():
        return []
    drafted = tomllib.loads(tier2_file.read_text())
    tier1_file = tier1_path(elocution_dir, system)
    doc = tomlkit.parse(tier1_file.read_text()) if tier1_file.exists() else tomlkit.document()
    added = []
    for siglum, entry in drafted.items():
        if siglum.startswith("_") or not _resolved(entry) or siglum in doc:
            continue
        table = tomlkit.inline_table()
        table["spoken"] = entry["spoken"]
        doc[siglum] = table
        added.append(siglum)
    if added:
        elocution_dir.mkdir(parents=True, exist_ok=True)
        tier1_file.write_text(tomlkit.dumps(doc))
    return added
