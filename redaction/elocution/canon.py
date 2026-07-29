"""The two external layers an open-vocabulary system's sigla table is built from.

A closed system's table (biblical.py, stephanus.py, ...) is finished, verified
Python and stays that way — the near-miss review is the right tool for a gap
there, and fixing one means a normal commit. An open system's table (starting
with classical.py) is never finished, so it gets two more layers on top of its
own hardcoded seed, weakest to strongest:

- **Tier 1**, ``<elocution_dir>/<system>.toml`` — this machine's shared,
  hand-curated canon, valid for every document. TOML rather than JSON
  specifically so an entry can carry a real comment recording *why* — the
  same provenance the closed tables keep inline, e.g. "collides with
  biblical's Numbers; classical wins the tie". Read with the stdlib
  ``tomllib``; only ``promote`` ever writes it, and does so with ``tomlkit``
  so a human's own comments and formatting survive a programmatic edit.
  Never touched by a draft sweep directly — an LLM's guess isn't evidence
  until a human decides to promote it.
- **Tier 2**, ``<work dir>/<system>.json`` — this one document's own
  entries, hand-edited or drafted (an eventual ``--elocution-draft``, on the
  ``lexicon.py`` pattern: additive, never overwriting). Plain JSON, matching
  ``lexicon.json``'s own precedent, since this file genuinely is written by
  tooling as well as by hand.

Precedence is seed < tier 1 < tier 2: a document's own file can override the
shared canon, which can override the hardcoded seed, each layer more specific
than the last. Keys starting with ``_`` are ignored, same convention as
``lexicon.py``, so a drafted file can carry its own bookkeeping without it
being read as a siglum.
"""

import json
import tomllib
from pathlib import Path

import tomlkit


def _tier1_path(elocution_dir: Path, system: str) -> Path:
    return elocution_dir / f"{system}.toml"


def _tier2_path(directory: Path, system: str) -> Path:
    return directory / f"{system}.json"


def _entries(data: dict) -> dict[str, str]:
    return {
        siglum: entry["spoken"]
        for siglum, entry in data.items()
        if not siglum.startswith("_") and "spoken" in entry
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
    return _entries(json.loads(path.read_text()))


def merged_sigla(
    seed: dict[str, str], elocution_dir: Path | None, directory: Path | None, system: str
) -> dict[str, str]:
    """``seed`` (hardcoded) overlaid by tier 1, overlaid by tier 2 — later wins."""
    return {
        **seed,
        **load_tier1(elocution_dir, system),
        **load_tier2(directory, system),
    }


def add_tier2(directory: Path, system: str, entries: dict[str, dict]) -> list[str]:
    """Merge drafted ``entries`` into tier 2, additive — an existing key is never touched.

    Mirrors ``lexicon.py``'s ``draft``: the file is the listener's (here,
    the reader's) to hand-edit, so a draft sweep only ever adds.
    """
    path = _tier2_path(directory, system)
    existing = json.loads(path.read_text()) if path.exists() else {}
    added = [siglum for siglum in entries if siglum not in existing]
    if added:
        merged = {**existing, **{siglum: entries[siglum] for siglum in added}}
        path.write_text(json.dumps(merged, ensure_ascii=False, indent=1, sort_keys=True))
    return added


def promote(elocution_dir: Path, directory: Path, system: str) -> list[str]:
    """Copy this document's tier-2 entries for ``system`` into the shared tier-1 canon.

    Additive only, same posture as ``add_tier2``: a siglum tier 1 already has
    is left exactly as it was, comments and all — this never resolves a
    disagreement between a document's own file and the shared canon, only
    fills in what tier 1 doesn't have yet. The one place tier 1 is ever
    written by code rather than by a human's editor, and even then only
    because a human ran this command to say so.
    """
    tier2_path = _tier2_path(directory, system)
    if not tier2_path.exists():
        return []
    drafted = json.loads(tier2_path.read_text())
    tier1_path = _tier1_path(elocution_dir, system)
    doc = tomlkit.parse(tier1_path.read_text()) if tier1_path.exists() else tomlkit.document()
    added = []
    for siglum, entry in drafted.items():
        if siglum.startswith("_") or "spoken" not in entry or siglum in doc:
            continue
        table = tomlkit.inline_table()
        table["spoken"] = entry["spoken"]
        doc[siglum] = table
        added.append(siglum)
    if added:
        elocution_dir.mkdir(parents=True, exist_ok=True)
        tier1_path.write_text(tomlkit.dumps(doc))
    return added
