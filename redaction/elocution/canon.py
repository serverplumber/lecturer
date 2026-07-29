"""The two external layers an open-vocabulary system's sigla table is built from.

A closed system's table (biblical.py, stephanus.py, ...) is finished, verified
Python and stays that way — the near-miss review is the right tool for a gap
there, and fixing one means a normal commit. An open system's table (starting
with classical.py) is never finished, so it gets two more layers on top of its
own hardcoded seed, weakest to strongest:

- **Tier 1**, ``<elocution_dir>/<system>.toml`` — this machine's shared,
  hand-curated canon, valid for every document. Only ``promote`` ever writes
  it, and does so with ``tomlkit`` so a human's own comments and formatting
  survive a programmatic edit. Never touched by a draft sweep directly — an
  LLM's guess isn't evidence until a human decides to promote it.
- **Tier 2**, ``<work dir>/<system>.toml`` — this one document's own entries,
  hand-edited or drafted (``draft-classical``, on the ``lexicon.py`` pattern:
  additive, never overwriting a resolved entry).

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
hand, with a head start rather than a blank line.
"""

import tomllib
from pathlib import Path

import tomlkit


def _tier1_path(elocution_dir: Path, system: str) -> Path:
    return elocution_dir / f"{system}.toml"


def _tier2_path(directory: Path, system: str) -> Path:
    return directory / f"{system}.toml"


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
    path = _tier1_path(elocution_dir, system)
    if not path.exists():
        return {}
    return _entries(tomllib.loads(path.read_text()))


def load_tier2(directory: Path | None, system: str) -> dict[str, str]:
    """This document's own entries for ``system``, siglum -> spoken form."""
    if directory is None:
        return {}
    path = _tier2_path(directory, system)
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


def _as_inline_table(entry: dict) -> tomlkit.items.InlineTable:
    """``entry``'s fields as an inline table — ``note`` excluded, it becomes a real comment."""
    table = tomlkit.inline_table()
    for key, value in entry.items():
        if key != "note":
            table[key] = value
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
    its key, not a field — see ``_as_inline_table``.
    """
    path = _tier2_path(directory, system)
    doc = tomlkit.parse(path.read_text()) if path.exists() else tomlkit.document()
    added = []
    for siglum, entry in entries.items():
        current = doc.get(siglum)
        if current is not None and (_resolved(current) or not _resolved(entry)):
            continue
        if note := entry.get("note"):
            doc.add(tomlkit.comment(note))
        doc[siglum] = _as_inline_table(entry)
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
    tier2_path = _tier2_path(directory, system)
    if not tier2_path.exists():
        return []
    drafted = tomllib.loads(tier2_path.read_text())
    tier1_path = _tier1_path(elocution_dir, system)
    doc = tomlkit.parse(tier1_path.read_text()) if tier1_path.exists() else tomlkit.document()
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
        tier1_path.write_text(tomlkit.dumps(doc))
    return added
