"""The ``redactions/<variant>/`` file-tree format: the interface between
redaction and recitation, read and written as plain text so a human can
inspect or hand-edit it between phases.
"""

import re
from pathlib import Path

from extraction import Extraction
from lecturer.workdir import section_stem
from redaction import Manner, NearMiss, RevertedParagraph, Script, ScriptSection, Utterance

_TAG = re.compile(r"^\[(\w+)(?: lang=([\w-]+))?\]$")


def write_sections(extraction: Extraction, directory: Path) -> Path:
    """Write each section to ``sections/NN_title.txt`` plus a footnotes file."""
    sections_dir = directory / "sections"
    sections_dir.mkdir(exist_ok=True)
    for index, section in enumerate(extraction.sections, start=1):
        stem = section_stem(index, section.title)
        (sections_dir / f"{stem}.txt").write_text(section.text + "\n")
        if section.footnotes:
            notes = "\n".join(f"[^{note.ref}]: {note.text}" for note in section.footnotes)
            (sections_dir / f"{stem}.footnotes.txt").write_text(notes + "\n")
    return sections_dir


def write_redactions(script: Script, directory: Path, variant: str) -> Path:
    """Write each redacted section to ``redactions/<variant>/NN_title.txt``.

    Weaving variants fork the tree, mirroring ``audio/``. Each file opens
    with a ``[section] title`` header so later phases can read the script
    back; utterances follow, separated by blank lines, each under a
    ``[manner]`` or ``[manner lang=xx]`` tag line. Notes no layer wove in
    are kept next door in ``.unwoven.txt`` files.
    """
    redactions_dir = directory / "redactions" / variant
    redactions_dir.mkdir(parents=True, exist_ok=True)
    for index, section in enumerate(script.sections, start=1):
        stem = section_stem(index, section.title)
        rendered = "\n\n".join(
            f"[{utterance.manner}{'' if utterance.lang == 'en' else f' lang={utterance.lang}'}]"
            f"\n{utterance.text}"
            for utterance in section.utterances
        )
        (redactions_dir / f"{stem}.txt").write_text(f"[section] {section.title}\n\n{rendered}\n")
        if section.footnotes:
            notes = "\n".join(f"[^{note.ref}]: {note.text}" for note in section.footnotes)
            (redactions_dir / f"{stem}.unwoven.txt").write_text(notes + "\n")
    return redactions_dir


def write_review(
    near_misses: list[NearMiss],
    reverted: list[RevertedParagraph],
    directory: Path,
    variant: str,
) -> Path | None:
    """Write ``redactions/<variant>/review.md``: two independent "look here" lists.

    Citations Elocutor couldn't convert, and paragraphs the glossator
    reverted to verbatim weaving — each its own section, neither a
    diagnosis. A near-miss is a known siglum sitting next to something
    locator-shaped the grammar didn't accept; a reverted paragraph is one
    whose model response either wasn't usable or didn't reproduce the
    source verbatim, so it fell back to the deterministic weave instead —
    and isn't cached, so a later ``redact --llm`` run will bill it again.
    Either way, enough context is given for a human to act by hand, not a
    guess at the underlying cause. Named ``.md``, not ``.txt``, so
    ``read_redactions``'s glob never mistakes it for a section. Always
    overwritten, even to "nothing to review" — never deleted, so a run
    invoked with a narrower ``systems`` set (or one that errors early)
    can't make an existing review vanish out from under someone reading it.
    """
    review_path = directory / "redactions" / variant / "review.md"
    if not near_misses and not reverted:
        review_path.write_text(
            f"# Review — {variant}\n\n"
            "Nothing to review — every citation-shaped span converted, and every "
            "paragraph sent to the model was glossed successfully.\n"
        )
        return None
    lines = [f"# Review — {variant}\n"]
    if near_misses:
        lines.append(f"## {len(near_misses)} citation-shaped span(s) Elocutor didn't convert\n")
        lines.append(
            "Not a diagnosis: a known siglum sits next to something locator-ish (a "
            "missing space, OCR noise, a shape the system doesn't cover...) that the "
            "grammar didn't accept. Check the context below and fix by hand if it's "
            "worth it.\n"
        )
        for miss in near_misses:
            lines.append(
                f'- **{miss.section}**, {miss.location} — `[{miss.system}]` "{miss.siglum}"'
            )
            lines.append(f"  > {miss.context}")
        lines.append("")
    if reverted:
        lines.append(f"## {len(reverted)} paragraph(s) reverted to verbatim weaving\n")
        lines.append(
            "Not cached, so a later `redact --llm` run retries (and re-bills) each of "
            "these — worth glossing by hand instead if one keeps failing. Not a "
            "diagnosis: the reason names what went wrong mechanically, not why.\n"
        )
        for paragraph in reverted:
            refs = ", ".join(f"[^{ref}]" for ref in paragraph.refs)
            lines.append(f"- **{paragraph.section_title}**, {refs} — {paragraph.reason}")
            lines.append(f"  > {paragraph.context}")
        lines.append("")
    review_path.write_text("\n".join(lines) + "\n")
    return review_path


def read_redactions(directory: Path, variant: str) -> Script | None:
    """Read a redacted script back from ``redactions/<variant>/``.

    The inverse of :func:`write_redactions` — this file tree is the
    interface between the redaction and recitation phases. Returns
    ``None`` when the variant has not been redacted yet.
    """
    redactions_dir = directory / "redactions" / variant
    files = sorted(
        path for path in redactions_dir.glob("*.txt") if not path.name.endswith(".unwoven.txt")
    )
    if not files:
        return None
    sections = []
    for path in files:
        blocks = path.read_text().split("\n\n")
        if blocks[0].startswith("[section]"):
            title = blocks[0].removeprefix("[section]").strip()
        else:
            title = path.stem  # pre-header files: slugified but serviceable
        utterances = []
        for block in blocks[1:]:
            tag, _, text = block.partition("\n")
            match = _TAG.match(tag.strip())
            if match is None or not text.strip():
                continue
            utterances.append(
                Utterance(
                    text=text.strip(),
                    manner=Manner(match.group(1)),
                    lang=match.group(2) or "en",
                )
            )
        sections.append(ScriptSection(title=title, utterances=utterances))
    return Script(sections=sections)
